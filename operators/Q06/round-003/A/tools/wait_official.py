"""Bounded GET-only observation; never creates or retries an official submission."""
import argparse
import time
import official_r003 as evidence

parser=argparse.ArgumentParser()
parser.add_argument('label')
args=parser.parse_args()
terminal={'Pass','Accepted','Fail','Wrong Answer','Compile Error','Runtime Error','Time Limit Exceeded','Memory Limit Exceeded','System Error'}
for attempt in range(24):
    evidence.poll(args.label)
    result=evidence.read(evidence.RAW/'runs'/args.label/'latest_check.json')
    if result['status'] in terminal:
        evidence.rank(args.label)
        raise SystemExit(0)
    time.sleep(20)
raise SystemExit('Observation interval ended; task still nonterminal, resume GET-only polling.')
