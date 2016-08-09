# spawnTracker 0.1.0(alpha)(unknown6 update)
## Probably the most efficient large area, long duration tracker for pokemon go data mining

You will need to provide a spawns.json file from [spawnScanner](https://github.com/TBTerra/spawnScan)

- only scans areas that have spawns in them when they should be active to maximise pokemon found per thread/account, assuming they are evenly spread across the hour
- supports multiple account scanning allowing larger number of pokemon per hour to be found
- Finds new spawns that where missed in initial scan (spawnScanner is about 97-98% accurate)

config.json is compatible with spawnScanner, the work section is used to confine newly found spawns to within the search boundaries. if no work section is present then no boundaries are set

###installation

- use python 2.7
- pip install -r requirements.txt
- fill out config.json
- have a spawns.json from spawnScan
- run track.py

###Things to do
- add some way of analysing and visualising the found data