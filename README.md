# spawnTracker 0.0.2(alpha)
## Probably the most efficient large area, long duration tracker for pokemon go data mining

You will need to provide a spawns.json file from [spawnScanner](https://github.com/TBTerra/spawnScan)

- Should handle around 10k spawns per thread/account, assuming they are evenly spread across the hour
- Should work on up to 16 threads/accounts. beyond that the number of spawns that can be handled per thread starts to drop, and total number of spawns handled remains constant
- Currently find new spawns that where missed in initial scan (spawnScanner is about 98% accurate) but does not yet add them to the spawns searched

config.json is compatible with spawnScanner, and while 'work' section is not currently used, it will be used to set boundary on where new spawns can be found (to avoid spawnpoints growing like a viral infection)

###Things to do

- make newly found spawns add to the spawns searched (as long as they are within work boundaries)
- add some way of analysing or visualising the found data