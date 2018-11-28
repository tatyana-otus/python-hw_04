# OTUServer
Multi-Process Event-Driven Web Server

## ab
```
ab -n 500000 -c 100 -r http://localhost:80/httptest/dir2/page.html
This is ApacheBench, Version 2.3 <$Revision: 1706008 $>
Copyright 1996 Adam Twiss, Zeus Technology Ltd, http://www.zeustech.net/
Licensed to The Apache Software Foundation, http://www.apache.org/

Benchmarking localhost (be patient)
Completed 50000 requests
Completed 100000 requests
Completed 150000 requests
Completed 200000 requests
Completed 250000 requests
Completed 300000 requests
Completed 350000 requests
Completed 400000 requests
Completed 450000 requests
Completed 500000 requests
Finished 500000 requests


Server Software:        OTUServer
Server Hostname:        localhost
Server Port:            80

Document Path:          /httptest/dir2/page.html
Document Length:        40 bytes

Concurrency Level:      100
Time taken for tests:   17.330 seconds
Complete requests:      500000
Failed requests:        0
Total transferred:      90500000 bytes
HTML transferred:       20000000 bytes
Requests per second:    28852.41 [#/sec] (mean)
Time per request:       3.466 [ms] (mean)
Time per request:       0.035 [ms] (mean, across all concurrent requests)
Transfer rate:          5099.89 [Kbytes/sec] received

Connection Times (ms)
              min  mean[+/-sd] median   max
Connect:        0    1   0.7      1       5
Processing:     0    3   1.2      2      23
Waiting:        0    3   1.2      2      22
Total:          0    3   1.5      3      24

Percentage of the requests served within a certain time (ms)
  50%      3
  66%      3
  75%      4
  80%      4
  90%      5
  95%      7
  98%      8
  99%      9
 100%     24 (longest request)
```
## wrk
```
wrk -t12 -c400 -d30s http://localhost:80/httptest/dir2/page.html
Running 30s test @ http://localhost:80/httptest/dir2/page.html
  12 threads and 400 connections
  Thread Stats   Avg      Stdev     Max   +/- Stdev
    Latency     6.73ms    3.43ms 207.60ms   88.70%
    Req/Sec     4.99k     1.62k    8.64k    56.11%
  1790747 requests in 30.09s, 317.65MB read
Requests/sec:  59503.35
Transfer/sec:     10.55MB
```
