import os
import json
import time
from operator import itemgetter

import threading

from pgoapi import PGoApi
from pgoapi.utilities import f2i

from google.protobuf.internal import encoder
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

def get_cellid(lat, long):
	origin = CellId.from_lat_lng(LatLng.from_degrees(lat, long)).parent(15)
	walk = [origin.id()]

	# 10 before and 10 after
	next = origin.next()
	prev = origin.prev()
	for i in range(10):
		walk.append(prev.id())
		walk.append(next.id())
		next = next.next()
		prev = prev.prev()
	return ''.join(map(encode, sorted(walk)))

def encode(cellid):
	output = []
	encoder._VarintEncoder()(output.append, cellid)
	return ''.join(output)

def doScan(sLat, sLng, sid, api):
	api.set_position(sLat,sLng,0)
	timestamp = "\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000"
	cellid = get_cellid(sLat, sLng)
	api.get_map_objects(latitude=f2i(sLat), longitude=f2i(sLng), since_timestamp_ms=timestamp, cell_id=cellid)
	response_dict = api.call()
	#print 'trying for poke'
	try:
		resp = response_dict['responses']
		map = resp['GET_MAP_OBJECTS']
		cells = map['map_cells']
	except KeyError:
		print ('error getting map data for {}, {}'.format(sLat, sLng))
		return
	except TypeError:
		print ('error getting map data for {}, {}'.format(sLat, sLng))
		return
	for cell in cells:
		curTime = cell['current_timestamp_ms']
		if 'wild_pokemons' in cell:
			for wild in cell['wild_pokemons']:
				if wild['time_till_hidden_ms']>0:
					timeSpawn = (curTime+(wild['time_till_hidden_ms']))-900000
					if wild['spawnpoint_id'] == sid:
						#print 'found poke'
						pokes.append({'time':timeSpawn, 'sid':wild['spawnpoint_id'], 'lat':wild['latitude'], 'lng':wild['longitude'], 'pid':wild['pokemon_data']['pokemon_id'], 'cell':CellId.from_lat_lng(LatLng.from_degrees(wild['latitude'], wild['longitude'])).to_token()})
						global Pfound
						Pfound += 1
					elif wild['spawnpoint_id'] not in Shash:
						print 'found new spawn'
						gmSpawn = time.gmtime(timeSpawn//1000)
						secSpawn = (gmSpawn.tm_min*60)+(gmSpawn.tm_sec)
						hash = '{},{}'.format(secSpawn,wild['spawnpoint_id'])
						Shash[wild['spawnpoint_id']] = secSpawn
						#spawns.insert(SbSearch(secSpawn),{'time':secSpawn, 'sid':wild['spawnpoint_id'], 'lat':wild['latitude'], 'lng':wild['longitude'], 'cell':CellId.from_lat_lng(LatLng.from_degrees(wild['latitude'], wild['longitude'])).to_token()})
						#if timeDif()>0
						###do somthing here

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
	global spawns, Shash
	#make own spawn list
	ownSpawns = []
	for i in xrange(wid,len(spawns),Tthreads):
		ownSpawns.append(spawns[i])
	print 'work list for worker {} is {} scans long'.format(wid,len(ownSpawns))
	#find start position
	pos = SbSearch(ownSpawns, (curSec()+60)%3600)
	#pos = SbSearch(ownSpawns, curSec())
	#while timeDif(curSec(),ownSpawns[pos]['time']) < 60:
	#	pos = ((pos+len(ownSpawns))-1) % len(ownSpawns)
	while True:
		#login
		api = PGoApi()
		api.set_position(0,0,0)
		if not api.login(config['auth_service'], config['users'][wid]['username'], config['users'][wid]['password']):
			print 'worker {} unable to log in. stoping.'.format(wid)
			return
		#iterate over
		while not paused:
			if not going:
				return
			if timeDif(curSec(),ownSpawns[pos]['time']) < 840:#if we arnt 14mins too late
				while timeDif(curSec(),ownSpawns[pos]['time']) < 60:#wait for 1 min past the spawn time
					time.sleep(1)
				doScan(ownSpawns[pos]['lat'],ownSpawns[pos]['lng'],ownSpawns[pos]['sid'],api)
			else:
				print 'posibly cant keep up. having to drop searches to catch up'
			pos = (pos+1) % len(ownSpawns)
		while paused:
			time.sleep(1)

def saver():
	print 'started saver thread'
	while True:
		time.sleep(3600)#wait 1 hour
		#tell workers to stop
		global paused, pokes
		paused = True
		time.sleep(0.5)
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
	print 'total of {} spawns to track'.format(len(spawns))
	#launch threads
	###todo: make it so it only launches the needed number of threads
	threads = []
	for user in config['users']:
		t = threading.Thread(target=worker, args = (len(threads),len(config['users'])))
		t.start()
		threads.append(t)
	saverT = threading.Thread(target=saver)
	saverT.start()
	time.sleep(2)
	#wait for stop signal
	while True:
		command = raw_input('Type stop and enter to stop program and save data\ntype prog to see how much data has been gathered ')
		if command == 'stop':
			going = False
			break
		elif command == 'prog':
			print 'currently had {} sightings'.format(Pfound)
	for t in threads:
		t.join()
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