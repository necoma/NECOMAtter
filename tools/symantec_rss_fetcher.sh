#!/bin/sh
cd /home/iimura/NECOMATter/tools
./rss_fetcher.py SYMANTEC_RSS_RISKS c55341552ddf714f97133fd6cfbbe91bcac82e404794fe9edb194a05b545e713 rss_symantec_risks.json
./rss_fetcher.py SYMANTEC_RSS_THREATS 7c73c4b554f2165f360f28745607a818be7a7bf33e0d9153e7bc25bea3fb9bd2 rss_symantec_threats.json
./rss_fetcher.py SYMANTEC_RSS_VULNERABILITIES 79d9d61637c8dff2e844adeb6806ea6201f3691e169dbd721bb7d26ac5d29be1 rss_symantec_vulnerabilities.json

