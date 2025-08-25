├── algorithms           # easily adjustable granular functions for core algorithm
│   ├── plateu_check.py  # predicate that checks the plateu
│   ├── ramp.py          # algo for ramping up the level of concurrency before we hit the plateu
│   ├── steady.py        # algo responsible for the steady state
|   ├── downloader.py    # algo that specifies the data we GET from the bject storages (cut the ranges, take the whole file)
│   └── warm_up.py       # algo for warming up an instance
├── ec2
│   └── ec2.py           # functionality related to the EC2 instance
├── observability        
│   ├── grafana.py       # grafana setup
│   ├── grafana.json     # grafana tables definition
│   └── scraper.py       # functionality for periodically scraping the prometheus to see the visualization in grafana
├── persistence          # storage related logic
│   ├── base.py          # the interface and tables definition
│   ├── parquet.py       # functoinality specific for parquet files
│   └── prom.py          # functoinality specific for prometheus database
├── results              # the output directory
├── systems              # setup and usage of systems under test
│   ├── aws.py           # AWS specific logic (so we can run it at the end to compare with R2)
│   ├── base.py          # the common interface for object storages
│   └── r2.py            # R2 specific logic (probably only the endpoint from the config, since R2 is compatible)
├── test
│   ├── benchmark_test.py   
│   └── check_test.py
├── README.md            # description of the experiment
├── benchmark.py         # 2 phase binary (benchmarking of the system)
├── check.py             # 1 phase binary (hit the R2 max throughput)
├── cli.py               # cli that helps to start the 0, 1, 2 phases and the visualiser with all the necessary flags
├── configuration.py     # constants and other configuration for the experiment 
├── requirements.txt
├── uploader.py          # 0 phase (upload a blob of data to the Object Storage)
└── visualiser.py        # draw various plots form the resulted parquet file
