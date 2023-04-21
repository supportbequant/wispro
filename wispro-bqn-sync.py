#!/usr/bin/python3

################################################################################
#
# Copyright (c) 2022 Bequant S.L.
# All rights reserved.
#
# This product or document is proprietary to and embodies the
# confidential technology of Bequant S.L., Spain.
# Possession, use, duplication or distribution of this product
# or document is authorized only pursuant to a valid written
# license from Bequant S.L.
#
#
################################################################################

# Avoid insecure warning when issuing REST queries
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

import argparse
import requests
import json
import logging

################################################################################

def printResponseDetails(rsp):
  logger = logging.getLogger(__name__)
  if logger.getEffectiveLevel() != logging.DEBUG:
    return

  logger.debug("")
  logger.debug("====== Request =======")
  logger.debug("%s to URL %s" % (rsp.request.method, rsp.request.url))
  for h in rsp.request.headers:
    logger.debug("%s: %s" % (h, rsp.request.headers[h]))
  logger.debug("")
  if rsp.request.body:
    logger.debug(rsp.request.body)
    logger.debug("")
  logger.debug("====== Response ======")
  logger.debug("HTTP/1.1 %d" % rsp.status_code)
  for h in rsp.headers:
    logger.debug("%s: %s" % (h, rsp.headers[h]))
  logger.debug("")
  logger.debug(json.dumps(rsp.json(), indent=4, separators=(',', ': ')))

################################################################################

def getWisproEntries(url, headers):

  page = 1
  remaining = True
  entries = []
  logger = logging.getLogger(__name__)

  while remaining:
    logger.info("GET to %s, page %d" % (url, page))
    rsp = requests.get(url, headers=headers, params={"page": page, "per_page": 100}, verify=False)  
    printResponseDetails(rsp)
    rspJson = rsp.json()
    if rspJson["status"] != 200:
      raise Exception("Bad query %d (page %d)" % (rspJson["status"], page))
    for e in rspJson["data"]:
      entries.append(e)
    total = rspJson["meta"]["pagination"]["total_records"]
    remaining = (total > len(entries))
    page += 1

  return entries

################################################################################

if __name__ == "__main__":

  parser = argparse.ArgumentParser(
    description="""
  Synchronizes speed limits in Wispro contracts with BQN rate policies.

  Requires an API KEY in Wispro and the REST API enabled in BQN.

  BQN Rate policies are identified by Wispro plan "name", with spaces replaced by undescores.
  BQN subscribers are identified by Wispro client "public-id".
  Contracts in status == "disabled" have their traffic blocked by BQN (Wispro_block policy).

  Known limitations:
  - Multiple IP addresses in same contract not supported (netmask must be "255.255.255.255").
  - Synchronization may take several minutes.
  - If the synchronization fails, no retry is attempted (must be don e externally).
  - No scheduling of scriot execution (must be done externally).
  """, formatter_class=argparse.RawTextHelpFormatter)

  parser.add_argument('-w', dest="wispro", type=str, default="www.cloud.wispro.co",
      help='Wispro billing URL (default www.cloud.wispro.co')
  parser.add_argument('-b', dest="bqn", type=str, default="192.168.0.120",
      help='BQN OAM IP (default 192.168.0.120')
  parser.add_argument('-v', '--verbose', action='count', dest='verbose', default=0,
                    help="Display extra informationt (repeat for increased verbosity)")
  parser.add_argument('user', metavar='BQN-USER', type=str, help='BQN REST API user')
  parser.add_argument('password', metavar='BQN-PASSWORD', type=str, help='BQN REST API password')
  parser.add_argument('key', metavar='API-KEY', type=str, help='Wispro REST API key')
  args = parser.parse_args()

  logger = logging.getLogger(__name__)
  if args.verbose == 0:
    logger.setLevel(logging.WARNING)
  elif args.verbose == 1:
    logger.setLevel(logging.INFO)
  else:
    logger.setLevel(logging.DEBUG)
  logging.basicConfig(format='%(asctime)s %(message)s', datefmt='%Y-%m-%dT%H:%M:%S')
  
  wisproUrl = "https://" + args.wispro + "/api/v1"
  wisproHeaders = {
   "Authorization": "%s" % args.key,
   "Accept": "application/json",
   "Accept-Encoding": "gzip, deflate",
   "Connection": "keep-alive"
  }

  plans = getWisproEntries(wisproUrl + '/plans', wisproHeaders)
  clients = getWisproEntries(wisproUrl + '/clients', wisproHeaders)
  contracts = getWisproEntries(wisproUrl + '/contracts', wisproHeaders)

  bqnUrl = "https://" + args.bqn + ":3443/api/v1"
  bqnHeaders = {
    "content-type": "application/json", 
    "Accept-Charset": "UTF-8"
  }

  for p in plans:
    planName = p["name"].replace(' ', '_')
    payload = {"policyId": "%s" % p["public_id"], "rateLimitDownlink": {"rate": p["ceil_down_kbps"]}, "rateLimitUplink": {"rate": p["ceil_up_kbps"]}}
    rsp = requests.post(bqnUrl + "/policies/rate/" + planName, headers=bqnHeaders, json=payload, auth=(args.user, args.password), verify=False) 
    printResponseDetails(rsp) 

  # Generate a block policy to enforce inactive clients
  blockPolicy = "Wispro_block"
  payload = {"policyId": "block", "rateLimitDownlink": {"rate": 0}, "rateLimitUplink": {"rate": 0}}
  rsp = requests.post(bqnUrl + "/policies/rate/" + blockPolicy, headers=bqnHeaders, json=payload, auth=(args.user, args.password), verify=False) 
  printResponseDetails(rsp)

  rsp = requests.get(bqnUrl + "/subscribers", auth=(args.user, args.password), verify=False)
  subsInBqn = rsp.json()["items"]
   
  logger.info('{:<15} {:<20} {:<9} {:<9} {:<8} {:<4} {:<12}'.format("IP", "PLAN", "Dn Kbps", "Up Kbs", "state", "Id", "Name"))
  for c in contracts:
    if c["netmask"] != "255.255.255.255":
      logger.warning("Contract with multiple IPs not supported (%s, mask %s)" % (c["ip"], c["netmask"]))
      continue
    matches = [x for x in clients if x["id"] == c["client_id"]]
    if len(matches) == 1:
      client = matches[0]
    else:
      logger.warning("Client not found (%s)" % c["client_id"])
      continue
    matches = [x for x in plans if x["id"] == c["plan_id"]]
    if len(matches) == 1:
      plan = matches[0]
    else:
      logger.warning("Plan not found (%s)" % c["plan_id"])
      continue
    logger.info('{:>15} {:<20} {:>9} {:>9} {:<8} {:>4} {:<12}'.format(c["ip"], plan["name"], plan["ceil_down_kbps"], plan["ceil_up_kbps"], c["state"], client["public_id"], client["name"]))

    # Inactive clients are blocked
    if c["state"] == "disabled":
      payload = {"subscriberId": "%s" % client["public_id"], "policyRate": "%s" % blockPolicy}
      rsp = requests.post(bqnUrl + "/subscribers/" + c["ip"], headers=bqnHeaders, json=payload, auth=(args.user, args.password), verify=False)
      printResponseDetails(rsp)
    else: # Look for limits to apply
      planName = plan["name"].replace(' ', '_')
      matches = [x for x in subsInBqn if x["subscriberIp"] == c["ip"]]
      if len(matches) == 1 and matches[0]["policyRate"] == planName:
        pass  # No update needed
      else:
        payload = {"subscriberId": "%s" % client["public_id"], "policyRate": "%s" % planName}
        rsp = requests.post(bqnUrl + "/subscribers/" + c["ip"], headers=bqnHeaders, json=payload, auth=(args.user, args.password), verify=False)
        printResponseDetails(rsp) 



