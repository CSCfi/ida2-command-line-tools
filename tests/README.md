<!--
This file is part of the IDA research data storage service

Copyright (C) 2018 Ministry of Education and Culture, Finland

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published
by the Free Software Foundation, either version 3 of the License,
or (at your option) any later version.

This program is distributed in the hope that it will be useful, but
WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero General Public
License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program. If not, see <http://www.gnu.org/licenses/>.

@author CSC - IT Center for Science Ltd., Espoo Finland <servicedesk@csc.fi>
@license GNU Affero General Public License, version 3
@link https://research.csc.fi/
-->

# IDA Command Line Tools - Automated Behavioral Tests

This subdirectory contains behavioral tests for the IDA command line tools.

Tests are typically run on a host on which there is a fully operational installation
of the IDA service, located in `/var/ida`; however, a subset of tests can be run against a remote IDA service instance using
only user credentials. This is useful for testing the command line tools from
various client environments which end users are likely to be using.

<pre>
WARNING: The automated tests will not run against the production IDA service. 

DO NOT ATTEMPT to configure and execute the automated tests against the production IDA service!

ONLY configure and execute automated tests against a development, test, or demo instance of the IDA service.
</pre>


## Initializing the Python Virtual Environment

The automated tests depend on a python virtual environment which must first be
initialized. Python version 3 must be installed on the host and the
python3 executable must be somewhere within the configured PATH. 

To initialize the python virtual environment, execute the script
`tests/utils/initialize-venv` in this git repository.


# Test Environment Configuration

If on a host on which there is an installation of IDA, the tests will utilize
the settings defined in the configuration file `/var/ida/config/config.sh` and
nothing special needs to be done to configure the test environment.

If on a host without any installation of IDA, the tests will be limited to 
those which can be executed only using user credentials, and will utilize the
same configuration files which are used by the command line tools; i.e.
`$HOME/.ida-config` and `$HOME/.netrc`

Define the variables `IDA_HOST` and `IDA_PROJECT` in `$HOME/.ida-config` and the
username and password credentials for the specified IDA host in `$HOME/.netrc`,
as documented in the command line tool user guide `README.md` in the root of
this git repository.


# Executing the Tests

To run the behavioral tests, simply execute the script
`tests/run-tests` located in this git repository.

**Note:** test data uploaded to the IDA host will be organized within a temporary root folder with a name based on the following pattern:

    test_YYYY-MM-DDT##:##:##Z_xxxxx

where `YYYY-MM-DDT##:##:##Z` corresponds to the UTC time when the execution of the tests began and `xxxxx` corresponds to a randomly generated unique token.

This temporary folder will be deleted automatically when all tests complete successfully. If any automated tests fail during execution, it will be necessary to delete this temporary folder manually from the staging and frozen areas of the configured test project on the specified IDA host.
