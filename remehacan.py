"""RemehaCAN implementation"""

import can

from const import (
	STATUSDICT,
	SUBSTATUSDICT,
	TXDATA
)

class RemehaCAN:
	"""RemehaCAN"""

	def __init__(self, channel, interface, can_transmit=False):
		"""Initialize connections"""
		self._bus = can.Bus(channel=channel, interface=interface)
		self._linecount_413f50 = 0
		self._linecount_410f34 = 0
		self._linecount_411d50 = 0
		self._data_requester = self._setup_data_requester(autostart=can_transmit)
		self._active_upload = False
		can.Notifier(self._bus, [self._sdo_upload_handler, self.parse_message])
		self.datadict = {}
		# temporary until I can be bothered to implement better segment parsing
		self._carrybyte = 0

	def __del__(self):
		"""Terminate can connection"""
		self._data_requester.stop()
		self._bus.shutdown()

	def _setup_data_requester(self, autostart=False):
		msg_list = []
		for msg in TXDATA:
			msg_list.append(can.Message(arbitration_id=0x241, data=msg, is_extended_id=False))
		return self._bus.send_periodic(msgs=msg_list, period=0.5, autostart=autostart)
		#msg_list = [can.Message(arbitration_id=0x241, data=[0x40, 0x1d, 0x50, 0x00, 0x00, 0x00, 0x00, 0x00], is_extended_id=False)]
		#return self._bus.send_periodic(msgs=msg_list, period=10, autostart=True)

	def _parse_int(self, bytevals, is_signed=True, scale=100):
		return int.from_bytes(bytevals, byteorder='little', signed=is_signed) / scale

	def _sdo_upload_handler(self, message):
		if message.arbitration_id == 0x1c1:
			# Upload started.
			if message.data.hex() == '411d50006c000000':
				self._active_upload = True
				#self._data_requester.stop()
				# Send initial upload request
				self._bus.send(msg=can.Message(arbitration_id=0x241, data=[0x60, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00], is_extended_id=False))
			elif self._active_upload == True:
				if message.data[0] == 0x00:
					self._bus.send(msg=can.Message(arbitration_id=0x241, data=[0x70, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00], is_extended_id=False))
				elif message.data[0] == 0x10:
					self._bus.send(msg=can.Message(arbitration_id=0x241, data=[0x60, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00], is_extended_id=False))
				# last segment or interfering segment received. Abort requesting segments
				else:
					self._active_upload = False
				#self._data_requester.start()

	def send_message(self, canid, message):
		return self._bus.send(can.Message(arbitration_id=canid, data=message, is_extended_id=False))

	def receive_message(self):
		return self._bus.recv()

	def parse_message(self, message):
		match message.arbitration_id:
			case 0x282:
				power = message.data[0]
				flow_temp = self._parse_int(message.data[1:3])
				self.datadict["power"] = power
				self.datadict["flow_temp"] = flow_temp
			case 0x381:
				outside_temp = self._parse_int(message.data[:2])
				outside_temp_avg_3min = self._parse_int(message.data[2:4])
				outside_temp_avg_2h = self._parse_int(message.data[4:6])
				self.datadict["outside_temp"] = outside_temp
				self.datadict["outside_temp_avg_3min"] = outside_temp_avg_3min
				self.datadict["outside_temp_avg_2h"] = outside_temp_avg_2h
			case 0x382:
				setpoint = self._parse_int(message.data[1:3])
				self.datadict["internal_setpoint"] = setpoint
			case 0x481:
				statuscode = message.data[0]
				substatuscode = message.data[1]
				backupstatuscode = message.data[5]
				pumpdhwstatuscode = message.data[6]
				# the least significant bit appears to indicate backup status
				if bool(backupstatuscode & 0b1):
					backupstatus = "ON"
				else:
					backupstatus = "OFF"
				if bool(backupstatuscode & 0b10):
					compressorstatus = "ON"
				else:
					compressorstatus = "OFF"
				# only this bit appears to indicate DHW status
				if bool(pumpdhwstatuscode & 0b10000):
					dhwstate = "ON"
				else:
					dhwstate = "OFF"
				# 0b100001 <- both these bits are always set when pump is active.
				# One probably corresponds to the outdoor unit pump, one with the
				# underfloor heating circuit pump connected to the control box
				if bool(pumpdhwstatuscode & 0b1):
					pumpstate = "ON"
				else:
					pumpstate = "OFF"

				statustext = STATUSDICT[statuscode]
				substatustext = SUBSTATUSDICT[substatuscode]
				self.datadict["status"] = statustext
				self.datadict["substatus"] = substatustext
				self.datadict["backupstatus"] = backupstatus
				self.datadict["dhwstatus"] = dhwstate
				self.datadict["compressorstatus"] = compressorstatus
				self.datadict["pumpstatus"] = pumpstate

			case 0x1c1 | 0x2c1 | 0x3c1:
				# This CAN ID contains a lot of data spanning multiple messages.
				# These messages are preceeded by identifiers.
				# The function only handles one message at a time, so we use
				# linecount variables to keep track of where we are in which
				# set of values.
				retdict = None
				if message.data[0:3].hex() == '413f50':
					self._linecount_413f50 = 1
					self._linecount_410f34 = 0
					self._linecount_411d50 = 0
					return
				elif message.data[0:3].hex() == '410f34':
					self._linecount_410f34 = 1
					self._linecount_413f50 = 0
					self._linecount_411d50 = 0
					return
				elif message.data[0:3].hex() == '411d50':
					self._linecount_411d50 = 1
					self._linecount_410f34 = 0
					self._linecount_413f50 = 0
					return
				# reset linecount on unknown or single-line objects
				elif 0x40 <= message.data[0] <= 0x4F:
					self._linecount_411d50 = 0
					self._linecount_410f34 = 0
					self._linecount_413f50 = 0
					# There are also some oneline values
					if message.data[0:3].hex() == '430050':
						ongridhours = self._parse_int(message.data[4:6], is_signed=False, scale=1)
						self.datadict["on_grid_hours"] = ongridhours
					elif message.data[0:3].hex() == '430b53':
						numstarts = self._parse_int(message.data[4:6], is_signed=False, scale=1)
						self.datadict["total_starts"] = numstarts
					elif message.data[0:3].hex() == '430c53':
						burnhours = self._parse_int(message.data[4:6], is_signed=False, scale=1)
						self.datadict["burner_hours"] = burnhours
					elif message.data[0:4].hex() == '432f5101':
						consenergy = self._parse_int(message.data[4:6], is_signed=False, scale=10)
						self.datadict["consumed_energy_total"] = consenergy
					elif message.data[0:4].hex() == '432f5102':
						consenergy = self._parse_int(message.data[4:6], is_signed=False, scale=10)
						self.datadict["consumed_energy_backup_total"] = consenergy
					elif message.data[0:4].hex() == '432c5101':
						consenergy = self._parse_int(message.data[4:6], is_signed=False, scale=10)
						self.datadict["consumed_energy_ch"] = consenergy
					elif message.data[0:4].hex() == '432c5102':
						consenergy = self._parse_int(message.data[4:6], is_signed=False, scale=10)
						self.datadict["consumed_energy_backup_ch"] = consenergy
					elif message.data[0:4].hex() == '432d5102':
						consenergy = self._parse_int(message.data[4:6], is_signed=False, scale=10)
						self.datadict["consumed_energy_backup_dhw"] = consenergy
					elif message.data[0:4].hex() == '432e5101':
						consenergy = self._parse_int(message.data[4:6], is_signed=False, scale=10)
						self.datadict["consumed_energy_cooling"] = consenergy
					elif message.data[0:3].hex() == '438550':
						energy_ch = self._parse_int(message.data[4:6], is_signed=False, scale=1)
						self.datadict["delivered_energy_heating"] = energy_ch
					elif message.data[0:3].hex() == '438650':
						energy_dhw = self._parse_int(message.data[4:6], is_signed=False, scale=1)
						self.datadict["delivered_energy_dhw"] = energy_dhw
					elif message.data[0:3].hex() == '438750':
						energy_cooling = self._parse_int(message.data[4:6], is_signed=False, scale=1)
						self.datadict["delivered_energy_cooling"] = energy_cooling
					elif message.data[0:3].hex() == '438950':
						energy_total = self._parse_int(message.data[4:6], is_signed=False, scale=1)
						self.datadict["delivered_energy_total"] = energy_total
					elif message.data[0:3].hex() == '43ad50':
						pumphours = self._parse_int(message.data[4:6], is_signed=False, scale=1)
						self.datadict["pump_hours"] = pumphours
					elif message.data[0:3].hex() == '43ae50':
						pumpstarts = self._parse_int(message.data[4:6], is_signed=False, scale=1)
						self.datadict["pump_starts"] = pumpstarts
					elif message.data[0:3].hex() == '43af50':
						backuphours = self._parse_int(message.data[4:6], is_signed=False, scale=1)
						self.datadict["backup_hours"] = backuphours
					elif message.data[0:3].hex() == '43b150':
						backupstarts = self._parse_int(message.data[4:6], is_signed=False, scale=1)
						self.datadict["backup_starts"] = backupstarts
					elif message.data[0:3].hex() == '43c143':
						defrostduration = self._parse_int(message.data[4:6], is_signed=False, scale=1)
						self.datadict["defrost_duration"] = defrostduration
					elif message.data[0:3].hex() == '43c243':
						defrostcycles = self._parse_int(message.data[4:6], is_signed=False, scale=1)
						self.datadict["defrost_cycles"] = defrostcycles
					elif message.data[0:3].hex() == '4b0454':
						roomtemp = self._parse_int(message.data[4:6], scale=10)
						self.datadict["room_temp"] = roomtemp
					elif message.data[0:3].hex() == '4b1954':
						roomsetpoint = self._parse_int(message.data[4:6], scale=10)
						self.datadict["room_setpoint"] = roomsetpoint
					elif message.data[0:3].hex() == '4b7943':
						heatpump_voltage = self._parse_int(message.data[4:6], scale=1)
						self.datadict["heatpump_voltage"] = heatpump_voltage
					elif message.data[0:3].hex() == '4b8043':
						inverter_temp = self._parse_int(message.data[4:6])
						self.datadict["inverter_temp"] = inverter_temp
					elif message.data[0:3].hex() == '4ba230':
						param_edits = self._parse_int(message.data[4:6], is_signed=False, scale=1)
						self.datadict["num_parameter_edits"] = param_edits
					elif message.data[0:3].hex() == '4f8a50':
						avgspf = self._parse_int(message.data[4:6], is_signed=False, scale=10)
						self.datadict["avg_spf"] = avgspf
					else:
						return
				# elif so we only enter this section on the following message
				elif message.data[0] == 0x00 or message.data[0] == 0x10:
					if self._linecount_413f50 >= 1:
		
						if self._linecount_413f50 == 1:
							pressure = message.data[5] /10
							am040 = self._parse_int(message.data[6:8])
							self.datadict["ch_pressure"] = pressure
							self.datadict["am040"] = am040
						elif self._linecount_413f50 == 3:
							#print(message.data)
							unknown = self._parse_int(message.data[7:8], True, 1)
							self.datadict["unknown1"] = unknown
						
						self._linecount_413f50 += 1
						# terminate because no other matches are possible
						return
	
					elif self._linecount_410f34 >= 1:	
						if self._linecount_410f34 == 1:
							locname = message.data[1:].strip(b'\x00').decode()
							self.datadict["locname"] = locname
						
						self._linecount_410f34 += 1
						return
	
					elif self._linecount_411d50 >= 1 and self._active_upload == True:
					# Though interesting, these values can more reliably be found in other CAN IDs
					#	if self._linecount_411d50 == 1:
					#		#intern setpunt
					#		am101 = self._parse_int(message.data[1:3])
					#		#setpnt aanvoerT WP
					#		hm003 = self._parse_int(message.data[3:5])
					#		#T aanvoer
					#		am016 = self._parse_int(message.data[5:7])
						if self._linecount_411d50 == 2:
							returntemp = self._parse_int(message.data[2:4])
							avgreturntemp = self._parse_int(message.data[4:6])
							#am027 = self._parse_int(message.data[6:8], scale=10)
							self.datadict["HM001"] = returntemp
							self.datadict["HM020"] = avgreturntemp
						elif self._linecount_411d50 == 4:
							# DM029
							dhwsetpoint = self._parse_int(message.data[2:4])
							refrigtemp = self._parse_int(message.data[6:8])
							self.datadict["refrigerant_temp"] = refrigtemp
							self.datadict["dhw_setpoint"] = dhwsetpoint
						elif self._linecount_411d50 == 5:
							condensortemp = self._parse_int(message.data[1:3])
							compintaketemp = self._parse_int(message.data[3:5])
							egresstemp = self._parse_int(message.data[5:7])
							# store first byte of evaporator temperature
							self._carrybyte = message.data[7:8]
							self.datadict["condensor_temp"] = condensortemp
							self.datadict["compressor_intake_temp"] = compintaketemp
							self.datadict["egress_temp"] = egresstemp
						elif self._linecount_411d50 == 6:
							evaptemp = self._parse_int(self._carrybyte + message.data[1:2])
							fanrpm = self._parse_int(message.data[2:4], False, 1)
							refrigpressure = self._parse_int(message.data[4:6], False, 10)
							hpmodul = message.data[6]
							compfreq = message.data[7]
							self.datadict["evaporator_temp"] = evaptemp
							self.datadict["heatpump_fanspeed"] = fanrpm
							self.datadict["refrigerant_pressure"] = refrigpressure
							self.datadict["heatpump_modulation"] = hpmodul
							self.datadict["compressor_frequency"] = compfreq
						elif self._linecount_411d50 == 7:
							# Store first byte of HM062
							self._carrybyte = message.data[7:8]
						elif self._linecount_411d50 == 8:
							compcurr = self._parse_int(self._carrybyte + message.data[1:2], False, 10)
							# flow rate
							am056 = self._parse_int(message.data[2:4], False)
							# flow outdoor unit
							#hm110 = self._parse_int(message.data[4:6], False)
							# store first byte of COP
							self._carrybyte = message.data[7:8]
							self.datadict["compressor_current"] = compcurr
							self.datadict["flow_rate"] = am056
						elif self._linecount_411d50 == 9:
							calculated_cop = self._parse_int(self._carrybyte + message.data[1:2], False, 1000)
							cop_threshold = self._parse_int(message.data[2:4], False, 1000)
							#hm110 = self._parse_int(message.data[4:6], False)
							self.datadict["cop"] = calculated_cop
							self.datadict["cop_threshold"] = cop_threshold
						elif self._linecount_411d50 == 14:
							airtemp = self._parse_int(message.data[2:4])
							self.datadict["air_temp"] = airtemp
						self._linecount_411d50 += 1
						return

if __name__=="__main__":
	remeha = RemehaCAN

	try:
		while True:
			print(remeha.parse_message(remeha.receive_message()))
	except KeyboardInterrupt:
		pass

