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

	def __del__(self):
		"""Terminate can connection"""
		self._data_requester.stop()
		self._bus.shutdown()

	def _setup_data_requester(self, autostart=False):
		msg_list = []
		for msg in TXDATA:
			msg_list.append(can.Message(arbitration_id=0x241, data=msg, is_extended_id=False))
		return self._bus.send_periodic(msgs=msg_list, period=1, autostart=True)

	def _parse_int(self, bytevals, is_signed=True, scale=100):
		return int.from_bytes(bytevals, byteorder='little', signed=is_signed) / scale

	def receive_message(self):
		return self._bus.recv()

	def parse_message(self, message):
		match message.arbitration_id:
			case 0x282:
				power = message.data[0]
				flow_temp = self._parse_int(message.data[1:3])
				return {"power": power,
						"flow_temp": flow_temp}
			case 0x381:
				outside_temp = self._parse_int(message.data[:2])
				outside_temp_avg_3min = self._parse_int(message.data[2:4])
				outside_temp_avg_2h = self._parse_int(message.data[4:6])
				return {"outside_temp": outside_temp,
						"outside_temp_avg_3min": outside_temp_avg_3min,
						"outside_temp_avg_2h": outside_temp_avg_2h}
			case 0x382:
				setpoint = self._parse_int(message.data[1:3])
				return {"internal_setpoint": setpoint}
			case 0x481:
				statuscode = message.data[0]
				substatuscode = message.data[1]
				backupstatuscode = message.data[5]
				# the least significant bit appears to indicate backup status
				if bool(backupstatuscode & 0b1):
					backupstatus = "ON"
				else:
					backupstatus = "OFF"
				if bool(backupstatuscode & 0b10):
					compressorstatus = "ON"
				else:
					compressorstatus = "OFF"
				dhwval = message.data[6]
				# only this bit appears to indicate DHW status
				if bool(dhwval & 0b10000):
					dhwstate = "ON"
				else:
					dhwstate = "OFF"

				statustext = STATUSDICT[statuscode]
				substatustext = SUBSTATUSDICT[substatuscode]
				return {"status": statustext,
						"substatus": substatustext,
						"backupstatus": backupstatus,
						"dhwstatus": dhwstate,
						"compressorstatus": compressorstatus}
			case 0x1c1:
				# This ID contains a lot of data spanning multiple messages.
				# They are however preceeded by some 'identifiers'.
				# These values probably have some actual meaning, but for now
				# We just check for these hardcoded values.
				# The function only handles one message at a time, so we use
				# linecount variables to keep track of where we are in what
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
						return {"on_grid_hours": ongridhours}
					elif message.data[0:3].hex() == '430b53':
						numstarts = self._parse_int(message.data[4:6], is_signed=False, scale=1)
						return {"total_starts": numstarts}
					elif message.data[0:3].hex() == '430c53':
						burnhours = self._parse_int(message.data[4:6], is_signed=False, scale=1)
						return {"burner_hours": burnhours}
					elif message.data[0:4].hex() == '432f5101':
						consenergy = self._parse_int(message.data[4:6], is_signed=False, scale=10)
						return {"consumed_energy_total": consenergy}
					elif message.data[0:4].hex() == '432f5102':
						consenergy = self._parse_int(message.data[4:6], is_signed=False, scale=10)
						return {"consumed_energy_backup_total": consenergy}
					elif message.data[0:4].hex() == '432c5101':
						consenergy = self._parse_int(message.data[4:6], is_signed=False, scale=10)
						return {"consumed_energy_ch": consenergy}
					elif message.data[0:4].hex() == '432c5102':
						consenergy = self._parse_int(message.data[4:6], is_signed=False, scale=10)
						return {"consumed_energy_backup_ch": consenergy}
					elif message.data[0:4].hex() == '432d5102':
						consenergy = self._parse_int(message.data[4:6], is_signed=False, scale=10)
						return {"consumed_energy_backup_dhw": consenergy}
					elif message.data[0:4].hex() == '432e5101':
						consenergy = self._parse_int(message.data[4:6], is_signed=False, scale=10)
						return {"consumed_energy_cooling": consenergy}
					elif message.data[0:3].hex() == '438550':
						energy_ch = self._parse_int(message.data[4:6], is_signed=False, scale=1)
						return {"delivered_energy_heating": energy_ch}
					elif message.data[0:3].hex() == '438650':
						energy_dhw = self._parse_int(message.data[4:6], is_signed=False, scale=1)
						return {"delivered_energy_dhw": energy_dhw}
					elif message.data[0:3].hex() == '438750':
						energy_cooling = self._parse_int(message.data[4:6], is_signed=False, scale=1)
						return {"delivered_energy_cooling": energy_cooling}
					elif message.data[0:3].hex() == '438950':
						energy_total = self._parse_int(message.data[4:6], is_signed=False, scale=1)
						return {"delivered_energy_total": energy_total}
					elif message.data[0:3].hex() == '43ad50':
						pumphours = self._parse_int(message.data[4:6], is_signed=False, scale=1)
						return {"pump_hours": pumphours}
					elif message.data[0:3].hex() == '43ae50':
						pumpstarts = self._parse_int(message.data[4:6], is_signed=False, scale=1)
						return {"pump_starts": pumpstarts}
					elif message.data[0:3].hex() == '43af50':
						backuphours = self._parse_int(message.data[4:6], is_signed=False, scale=1)
						return {"backup_hours": backuphours}
					elif message.data[0:3].hex() == '43b150':
						backupstarts = self._parse_int(message.data[4:6], is_signed=False, scale=1)
						return {"backup_starts": backupstarts}
					elif message.data[0:3].hex() == '43c143':
						defrostduration = self._parse_int(message.data[4:6], is_signed=False, scale=1)
						return {"defrost_duration": defrostduration}
					elif message.data[0:3].hex() == '43c243':
						defrostcycles = self._parse_int(message.data[4:6], is_signed=False, scale=1)
						return {"defrost_cycles": defrostcycles}
					elif message.data[0:3].hex() == '4b0454':
						roomtemp = self._parse_int(message.data[4:6], scale=10)
						return {"room_temp": roomtemp}
					elif message.data[0:3].hex() == '4b1954':
						roomsetpoint = self._parse_int(message.data[4:6], scale=10)
						return {"room_setpoint": roomsetpoint}
					elif message.data[0:3].hex() == '4ba230':
						param_edits = self._parse_int(message.data[4:6], is_signed=False, scale=1)
						return {"num_parameter_edits": param_edits}
					elif message.data[0:3].hex() == '4f8a50':
						avgspf = self._parse_int(message.data[4:6], is_signed=False, scale=10)
						return {"avg_spf": avgspf}
					else:
						return
				# elif so we only enter this section on the following message
				elif self._linecount_413f50 >= 1:
	
					if self._linecount_413f50 == 1:
						pressure = message.data[5] /10
						am040 = self._parse_int(message.data[6:8])
						retdict = {"ch_pressure": pressure,
								"am040": am040}
					elif self._linecount_413f50 == 3:
						#print(message.data)
						unknown = self._parse_int(message.data[7:8], True, 1)
						retdict = {"unknown1": unknown}
					
					self._linecount_413f50 += 1
					# terminate because no other matches are possible
					return retdict

				elif self._linecount_410f34 >= 1:	
					if self._linecount_410f34 == 1:
						locname = message.data.strip(b'\x00').decode()
						retdict = {"locname": locname}
					
					self._linecount_410f34 += 1
					return retdict

				elif self._linecount_411d50 >= 1:
	
					if self._linecount_411d50 == 2:
						returntemp = self._parse_int(message.data[2:4])
						avgreturntemp = self._parse_int(message.data[4:6])
						retdict = {"HM001": returntemp,
								"HM020": avgreturntemp}
					elif self._linecount_411d50 == 4:
						refrigtemp = self._parse_int(message.data[6:8])
						retdict = {"refrigerant_temp": refrigtemp}
					elif self._linecount_411d50 == 5:
						condensortemp = self._parse_int(message.data[1:3])
						egresstemp = self._parse_int(message.data[5:7])
						retdict = {"condensor_temp": condensortemp,
								"egress_temp": egresstemp}
					elif self._linecount_411d50 == 6:
						fanrpm = self._parse_int(message.data[2:4], False, 1)
						refrigpressure = self._parse_int(message.data[4:6], False, 10)
						hpmodul = message.data[6]
						compfreq = message.data[7]
						retdict = {"heatpump_fanspeed": fanrpm,
								"refrigerant_pressure": refrigpressure,
								"heatpump_modulation": hpmodul,
								"compressor_frequency": compfreq}
					elif self._linecount_411d50 == 8:
						am056 = self._parse_int(message.data[2:4], False)
						#hm110 = self._parse_int(message.data[4:6], False)
						retdict = {"flow_rate": am056}
					self._linecount_411d50 += 1
					return retdict

if __name__=="__main__":
	remeha = RemehaCAN

	try:
		while True:
			print(remeha.parse_message(remeha.receive_message()))
	except KeyboardInterrupt:
		pass

