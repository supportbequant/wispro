# wispro-bqn-sync

Simple synchronization script between BQN and a Wispro billing.

## Installation

The script requires python 3.10 or later with *requests* package.

### In Arch Linux:
`$ sudo pacman -S python3`

`$ sudo pip3 install requests`

### In Windows:
1. In elevated (administration) shell:

`> winget install python`

2. In normal shell:

`> pip install requests`

#### In Mac OS:
1. Download package for Mac from python official site:

https://www.python.org/downloads/macos/

2. Install package (enter Administrator password when requested)

4. In command shell:

`$ pip3 install requests`

## Setup

Create an API token in Wispro billing.

Enable REST API in BQN.

## Running the script

Every time a synchronization is needed:

`python3 ./wispro-bqn-sync.py -b <bqn-ip> <bqn-rest-user> <bqn-rest-password> <wispro-api-token>`

## Known limitations

- Multiple IP addresses in same client are not supported.
- The first time it may take minutes to run. Following executions will send to BQN only client changes and will be quicker.
- If the synchronization fails, no retry is attempted (must be done externally).
- No scheduling of script execution (must be done externally).

## Relation of BQN entities to Wisphub schema

- BQN Rate policies are identified by Wispro plan "name", with spaces replaced by undescores.
- BQN subscribers are identified by Wispro client "public-id".
- Contracts in status == "disabled" have their traffic blocked by BQN (Wispro_block policy).

