# spawnTracker 0.0.5(alpha)
## Probably the most efficient large area, long duration tracker for pokemon go data mining

You will need to provide a spawns.json file from [spawnScanner](https://github.com/TBTerra/spawnScan)

- Should handle around 10k spawns per thread/account, assuming they are evenly spread across the hour
- Should work on up to 16 threads/accounts. beyond that the number of spawns that can be handled per thread starts to drop, and total number of spawns handled remains constant
- Finds new spawns that where missed in initial scan (spawnScanner is about 97-98% accurate)

config.json is compatible with spawnScanner, the work section is used to confine newly found spawns to within the search boundaries. if no work section is present then no boundaries are set

###Things to do
- add some way of analysing and visualising the found data