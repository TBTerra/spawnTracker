import os
import logging
import json
import time
from operator import itemgetter

import threading
import utils

from pgoapi import pgoapi
from pgoapi import utilities as util
from pgoapi.exceptions import ServerSideRequestThrottlingException

from s2sphere import CellId, LatLng

pokes = []
spawns = []
Shash = {}
going = True
paused = False
Pfound = 0

#config file
with open('config.json') as file:
	config = json.load(file)

def withinWork(lat, lng):
	if 'work' not in config:
		return True
	for rect in config['work']:
		if (lat>rect[0]) or (lat<rect[2]):
			continue
		if (lng<rect[1]) or (lng>rect[3]):
			continue
		return True
	return False

def curSec():
	return (60 * time.gmtime().tm_min) + time.gmtime().tm_sec
	
def timeDif(a,b):#timeDif of -1800 to +1800 secs
	dif = a-b
	if (dif < -1800):
		dif += 3600
	if (dif > 1800):
		dif -= 3600
	return dif

def SbSearch(Slist, T):
	#binary search to find the lowest index with the required value or the index with the next value update
	first = 0
	last = len(Slist)-1
	while first < last:
		mp = (first+last)//2
		if Slist[mp]['time'] < T:
			first = mp + 1
		else:
			last = mp
	return first
	
def worker(wid,Tthreads):
	global spawns, Shash, going
	#make own spawn list
	ownSpawns = []
	for i in xrange(wid,len(spawns),Tthreads):
		ownSpawns.append(spawns[i])
	print 'work list for worker {} is {} scans long'.format(wid,len(ownSpawns))
	#find start position
	pos = SbSearch(ownSpawns, (curSec()+3540)%3600)
	
	api = pgoapi.PGoApi(provider=config['auth_service'], username=config['users'][wid]['username'], password=config['users'][wid]['password'], position_lat=0, position_lng=0, position_alt=0)
	api.activate_signature(utils.get_encryption_lib_path())
	
	while True:
		#iterate over
		while not paused:
			if not going:
				return
			if timeDif(curSec(),ownSpawns[pos]['time']) < 840:#if we arnt 14mins too late
				while timeDif(curSec(),ownSpawns[pos]['time']) < 60:#wait for 1 min past the spawn time
					time.sleep(1)
				sLat = ownSpawns[pos]['lat']
				sLng = ownSpawns[pos]['lng']
				sid = ownSpawns[pos]['sid']
				api.set_position(sLat,sLng,0)
				cell_ids = util.get_cell_ids(lat=sLat, long=sLng, radius=80)
				timestamps = [0,] * len(cell_ids)
				while True:
					try:
						response_dict = api.get_map_objects(latitude = sLat, longitude = sLng, since_timestamp_ms = timestamps, cell_id = cell_ids)
					except  ServerSideRequestThrottlingException:
						config['scanDelay'] += 0.5
						print ('kk.. increasing sleep by 0.5 to [}').format(sleepperscan)
						time.sleep(config['scanDelay'])
						continue
					except:
						time.sleep(config['scanDelay'])
						api.set_position(sLat,sLng,0)
						time.sleep(config['scanDelay'])
						continue
					break
				try:
					resp = response_dict['responses']
					map = resp['GET_MAP_OBJECTS']
					cells = map['map_cells']
				except KeyError:
					print ('thread {} error getting map data for {}, {}'.format(wid,sLat, sLng))
					time.sleep(config['scanDelay'])
					continue
				except TypeError:
					print ('thread {} error getting map data for {}, {}'.format(wid,sLat, sLng))
					time.sleep(config['scanDelay'])
					continue
				gotit = False
				for cell in cells:
					curTime = cell['current_timestamp_ms']
					if 'wild_pokemons' in cell:
						for wild in cell['wild_pokemons']:
							if wild['time_till_hidden_ms']>0:
								timeSpawn = (curTime+(wild['time_till_hidden_ms']))-900000
								if wild['spawn_point_id'] == sid:
									gotit = True
									pokes.append({'time':timeSpawn, 'sid':wild['spawn_point_id'], 'lat':wild['latitude'], 'lng':wild['longitude'], 'pid':wild['pokemon_data']['pokemon_id'], 'cell':CellId.from_lat_lng(LatLng.from_degrees(wild['latitude'], wild['longitude'])).to_token()})
									global Pfound
									Pfound += 1
									
								elif wild['spawn_point_id'] not in Shash:
									print 'found new spawn'
									gmSpawn = time.gmtime(timeSpawn//1000)
									secSpawn = (gmSpawn.tm_min*60)+(gmSpawn.tm_sec)
									hash = '{},{}'.format(secSpawn,wild['spawn_point_id'])
									Shash[wild['spawn_point_id']] = secSpawn
									if withinWork(wild['latitude'],wild['longitude']):
										spawnLog = {'time':secSpawn, 'sid':wild['spawn_point_id'], 'lat':wild['latitude'], 'lng':wild['longitude'], 'cell':CellId.from_lat_lng(LatLng.from_degrees(wild['latitude'], wild['longitude'])).to_token()}
										spawns.append(spawnLog)
										index = SbSearch(ownSpawns,secSpawn)
										ownSpawns.insert(index,spawnLog)
										if pos>index:
											pos += 1
										if timeDif(ownSpawns[pos]['time'],secSpawn)>0:#only bother to add it to the found pokes, if it has missed its scan window
											pokeLog = {'time':timeSpawn, 'sid':wild['spawn_point_id'], 'lat':wild['latitude'], 'lng':wild['longitude'], 'pid':wild['pokemon_data']['pokemon_id'], 'cell':CellId.from_lat_lng(LatLng.from_degrees(wild['latitude'], wild['longitude'])).to_token()}
											pokes.append(pokeLog)
											Pfound += 1
									else:
										print 'not in work area'
				if not gotit:
					print 'couldnt find spawn'
			else:
				print 'posibly cant keep up. having to drop searches to catch up'
			pos = (pos+1) % len(ownSpawns)
			time.sleep(config['scanDelay'])
		while paused:
			time.sleep(1)

def saver():
	print 'started saver thread'
	while True:
		countdown = 3600
		while countdown > 0:
			if not going:
				return
			countdown -= 1
			time.sleep(1)#wait 1 hour
		#tell workers to stop
		global paused, pokes
		paused = True
		time.sleep(0.5)#dosnt garentee all workers have stoped, but should mean that all workers have got to their sleep sections
		print 'pausing work to save (currently seen {} pokemon)'.format(Pfound)
		#save the new pokes
		if os.path.isfile('pokes.json'):
			with open('pokes.json') as file:
				temp = json.load(file)
				temp.extend(pokes)
				f = open('pokes.json','w')
				json.dump(temp,f)
				f.close()
				file.close()
		else:
			f = open('pokes.json','w')
			json.dump(pokes,f)
			f.close()
		#clear poke buffer
		pokes = []
		print 'resuming work'
		paused = False

def main():
	global spawns, Shash, going
	#load spawn points
	with open('spawns.json') as file:
		spawns = json.load(file)
		file.close()
	for spawn in spawns:
		hash = '{},{}'.format(spawn['time'],spawn['sid'])
		Shash[spawn['sid']] = spawn['time']
	#sort spawn points
	spawns.sort(key=itemgetter('time'))
	useThreads = ((len(spawns)-1)//len(config['users']))+1
	print 'total of {} spawns to track, going to use {} threads'.format(len(spawns),useThreads)
	if useThreads > len(config['users']):
		print 'not enough threads in config file, stopping'
		return
	#launch threads
	###todo: make it so it only launches the needed number of threads
	threads = []
	for i in range(useThreads):
		t = threading.Thread(target=worker, args = (i,useThreads))
		t.start()
		threads.append(t)
	saverT = threading.Thread(target=saver)
	saverT.start()
	time.sleep(2)
	#wait for stop signal
	while True:
		command = raw_input('Type stop and enter to stop program and save data\ntype prog to see how much data has been gathered\n')
		if command == 'stop':
			going = False
			break
		elif command == 'prog':
			print 'currently had {} sightings'.format(Pfound)
	for t in threads:
		t.join()
	saverT.join()
	print 'tracker stoped, had {} pokemeon sightings'.format(Pfound)
	#print to file
	if os.path.isfile('pokes.json'):
		with open('pokes.json') as file:
			temp = json.load(file)
			temp.extend(pokes)
			f = open('pokes.json','w')
			json.dump(temp,f)
			f.close()
			file.close()
	else:
		f = open('pokes.json','w')
		json.dump(pokes,f)
		f.close()
	
	with open('spawns.json','w') as file:
		json.dump(spawns,file)
		file.close()

if __name__ == '__main__':
	main()
