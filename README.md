# Blockchain-Based-Voting-System
Simple blockchain project with the ability to host and vote on polls. Features a p2p protocol and example wallet software.

# Required libraries

* [ecdsa](https://pypi.org/project/ecdsa/) (0.16.1)
* [Kivy](https://kivy.org/#home) (2.0.0)
* [Cyrptography](https://pypi.org/project/cryptography/) (3.4.7)

Stated versions of these module will work whereas updated versions haven't been tested with this project. 

# Running the Code
Ensure that all files are in the same folder. 

Execute main.py

To begin mining, the device running the code must have made a connection to the p2p network.

Project has been designed to run on local networks. 

# How the Blockchain works
The blockchain stores transactions of tokens. These tokens can be transfered between addresses like a currency and are then converted into balllot papers by a 'poll host.' 

Each ballot paper is assigned to a 'voter' - only the owner of the voter address can submit the ballot. 

There are three types of transactions:

1. Transfer of 'empty' tokens
2. Assignement of an empty token to a poll and a voter
3. Submission of a vote
