# --------------------------------------------------------------------------------
# This file is part of the IDA research data storage service
#
# Copyright (C) 2018 Ministry of Education and Culture, Finland
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License,
# or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
# or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero General Public
# License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
# @author   CSC - IT Center for Science Ltd., Espoo Finland <servicedesk@csc.fi>
# @license  GNU Affero General Public License, version 3
# @link     https://research.csc.fi/
# --------------------------------------------------------------------------------

import os
import sys
import socket
import importlib.util
from pathlib import Path


def _load_module_from_file(module_name, file_path):
    try:
        # python versions >= 3.5
        module_spec = importlib.util.spec_from_file_location(module_name, file_path)
        module = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(module)
    except AttributeError:
        # python versions < 3.5
        from importlib.machinery import SourceFileLoader
        module = SourceFileLoader(module_name, file_path).load_module()
    return module


def load_configuration():

    cli_root = os.environ.get("IDA_CLI_ROOT", None)
    if cli_root == None:
        sys.exit("Error: The variable IDA_CLI_ROOT must be defined! Aborting")

    # Derive the test configuration from a configuration file with the following
    # priority, taking the first file that exists:
    #     $IDA_CLI_ROOT/tests/config/config.sh
    #     /var/ida/config/config.sh
    #     $HOME/.ida-config
    # If no configuration file can be found, abort.
    #
    # User account credentials can be defined in either the configuration file,
    # or (better) in the ~/.netrc file. Thus, all tests based on user credentials
    # will work when the user executing the tests has configured their environment
    # as recommended for the 'ida' command line tools script.

    config_located = False

    config_path = "%s/tests/config/config.sh" % cli_root
    if Path(config_path).is_file():
        config_source = "TEST" # Automated tests config
        config_located = True

    #config_located = False # TEMP HACK

    if not config_located:
        config_path = "/var/ida/config/config.sh"
        if Path(config_path).is_file():
            config_source = "IDA" # IDA service config
            config_located = True

    #config_located = False # TEMP HACK

    if not config_located:
        config_path = "%s/.ida-config" % os.environ["HOME"]
        if Path(config_path).is_file():
            config_source = "CLI" # IDA CLI config
            config_located = True

    if not config_located:
        sys.exit("Error: unable to locate any usable configuration! Aborting")

    server_configuration = _load_module_from_file("server_configuration.variables", config_path)

    ida_host = getattr(server_configuration, "IDA_HOST", "https://%s" % socket.gethostname())

    # Construct configuration dictionary
    config = {
        "CONFIG_SOURCE":           config_source,
        "CONFIG_PATH":             config_path,
        "PROJECT_USER_PREFIX":     "PSO_",
        "STAGING_FOLDER_SUFFIX":   "+",
        "MAX_FILE_COUNT":          5000,
        "IDA_CLI_ROOT":            cli_root,

        "IDA_ENVIRONMENT":         getattr(server_configuration, "IDA_ENVIRONMENT", "DEV"),
        "DEBUG":                   getattr(server_configuration, "DEBUG", "false"),
        "NO_FLUSH_AFTER_TESTS":    getattr(server_configuration, "NO_FLUSH_AFTER_TESTS", "false"),

        "IDA_HOST":                ida_host,
        "IDA_PROJECT":             getattr(server_configuration, "IDA_PROJECT", None),
        "IDA_USERNAME":            getattr(server_configuration, "IDA_USERNAME", None),
        "IDA_PASSWORD":            getattr(server_configuration, "IDA_PASSWORD", None),

        "IDA_API_ROOT_URL":        getattr(server_configuration, "IDA_API_ROOT_URL", "%s/apps/ida/api" % ida_host),
        "URL_BASE_IDA":            getattr(server_configuration, "URL_BASE_IDA", "%s/apps/ida" % ida_host),
        "URL_BASE_SHARE":          getattr(server_configuration, "URL_BASE_SHARE", "%s/ocs/v1.php/apps/files_sharing/api/v1/shares" % ida_host),
        "URL_BASE_FILE":           getattr(server_configuration, "URL_BASE_FILE", "%s/remote.php/webdav" % ida_host),
        "URL_BASE_GROUP":          getattr(server_configuration, "URL_BASE_GROUP", "%s/ocs/v1.php/cloud/groups" % ida_host),

        "TEST_USER_PASS":          getattr(server_configuration, "TEST_USER_PASS", "test"),
        "NC_ADMIN_USER":           getattr(server_configuration, "NC_ADMIN_USER", "admin"),
        "NC_ADMIN_PASS":           getattr(server_configuration, "NC_ADMIN_PASS", None),

        "ROOT":                    getattr(server_configuration, "ROOT", None),
        "STORAGE_OC_DATA_ROOT":    getattr(server_configuration, "STORAGE_OC_DATA_ROOT", None),

        "RUN_TESTS_IN_PRODUCTION": getattr(server_configuration, "RUN_TESTS_IN_PRODUCTION", None) # Really don't do this
    }

    if os.path.exists("/etc/httpd/"):
        config['HTTPD_USER'] = "apache"
    else:
        config['HTTPD_USER'] = "www-data"

    return config
