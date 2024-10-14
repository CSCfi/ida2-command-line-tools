# --------------------------------------------------------------------------------
# This file is part of the IDA research data storage service
#
# Copyright (C) 2019 Ministry of Education and Culture, Finland
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
# Note regarding sequence of tests: this test case contains only a single test
# method, which utilizes the test projects, user accounts, and project data
# initialized during setup, such that the sequential actions in the single
# test method create side effects which subsequent actions and assertions may
# depend on. The state of the test accounts and data must be taken into account
# whenever adding tests at any particular point in that execution sequence.
#
# Note regarding zero size files: proper handling of zero size files is
# primarily tested by including zero size files in the pre-defined test
# data and ensuring that on copy and move operations, a selected zero size
# file is included as expected in the target location.
# --------------------------------------------------------------------------------

import requests
import unittest
import subprocess
import os
import sys
import shutil
import json
import secrets
import datetime
import time

from pathlib import Path
from tests.common.utils import load_configuration

class TestIdaCli(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        print("=== tests/cli/test_cli")

    def setUp(self):

        print("(initializing)")

        self.config = load_configuration()

        # timeout when waiting for actions to complete
        self.timeout = 10800 # 3 hours

        self.cli_root = self.config["IDA_CLI_ROOT"]
        self.cli_cmd = "%s/ida" % self.cli_root
        self.tempdir = "%s/tests/cli/tmp" % (self.cli_root)
        self.ignore_file = "-i %s/tests/cli/ida-ignore" % (self.cli_root)
        self.config_file = "%s/ida-config" % self.tempdir
        self.info_args = "-c %s" % self.config_file
        self.args = "-V %s" % self.info_args
   
        self.ida_host = self.config["IDA_HOST"]
        self.ida_api = self.config["IDA_API_ROOT_URL"]

        self.config_source = self.config["CONFIG_SOURCE"]

        if self.config_source == "IDA":
            self.test_project_name = "test_cli_project"
            self.test_user_name = "test_cli_user"
            self.test_user_pass = self.config["TEST_USER_PASS"]
            self.admin_user_name = self.config["NC_ADMIN_USER"]
            self.admin_user_pass = self.config["NC_ADMIN_PASS"]
        else: # "TEST" or "HOME"
            self.test_project_name = self.config["IDA_PROJECT"]
            self.test_user_name = self.config.get("IDA_USERNAME", None)
            self.test_user_pass = self.config.get("IDA_PASSWORD", None)
            self.admin_user_name = self.config.get("NC_ADMIN_USER", "admin")
            self.admin_user_pass = self.config.get("NC_ADMIN_PASS", None)

        self.assertIsNotNone(self.ida_host)
        self.assertIsNotNone(self.test_project_name)

        self.pso_user_name = "%s%s" % (self.config["PROJECT_USER_PREFIX"], self.test_project_name)
        self.test_user_auth = (self.test_user_name, self.test_user_pass)
        self.admin_user_auth = (self.admin_user_name, self.admin_user_pass)

        self.ida_root = self.config.get("ROOT", None)
        self.storage_root = self.config.get("STORAGE_OC_DATA_ROOT", None)
        self.testdata = "%s/tests/testdata" % (self.config["IDA_CLI_ROOT"])

        # Adjust authentication if netrc will be used, due to no username/password defined in configuration
        self.netrc = False
        if self.config_source == "HOME" and self.test_user_name == None and self.test_user_pass == None:
            self.netrc = True
            self.test_user_auth = None

        # Generate random test execution token, to make uploaded data directory unique
        self.token = "_%sZ_%s" % (datetime.datetime.now().replace(microsecond=0).isoformat(), secrets.token_hex(3))

        self.staging = "%s/%s/files/%s+" % (self.storage_root, self.pso_user_name, self.test_project_name)
        self.frozen = "%s/%s/files/%s" % (self.storage_root, self.pso_user_name, self.test_project_name)

        # Ensure CLI script exists where specified
        path = Path(self.cli_cmd)
        self.assertTrue(path.is_file())

        # Prefix IDA CLI script pathname with environment variable allowing use of modified script
        self.cli_cmd = "ALLOW_MODIFIED_SCRIPT=\"true\" %s" % self.cli_cmd

        # Prefix IDA CLI script pathname with user password from configuration if netrc not being used.
        # This prevents a user's actual password taken from a home configuration from being included in
        # any of the temporary configuration files generated as part of these tests
        if not self.netrc:
            self.cli_cmd = "IDA_PASSWORD=\"%s\" %s" % (self.test_user_pass, self.cli_cmd)

        # Ensure test data root exists where specified and is directory
        path = Path(self.testdata)
        self.assertTrue(path.is_dir())

        # Ensure temp dir exists and is empty
        path = Path(self.tempdir)
        if path.exists():
            shutil.rmtree(self.tempdir, ignore_errors=True)
        path.mkdir()

        # If the loaded configuration was from a locally installed version of IDA, then the full scope of localized
        # tests will be run; else, only a limited subset of tests will be run against a remote IDA instance
        
        self.run_localized_tests = self.config_source == "IDA"

        # Determine whether trusted tests should be run, based on defined credentials
        
        self.run_trusted_tests = False

        if self.config.get("NC_ADMIN_PASS", None) != None:
            self.run_trusted_tests = True

        # Allow manual override of local and trusted tests
        if os.getenv('ONLY_SAFE_TESTS') == 'true':
            self.run_localized_tests = False
            self.run_trusted_tests = False

        print("CONFIG SOURCE:           %s" % self.config_source)
        print("CONFIG PATH:             %s" % self.config["CONFIG_PATH"])
        print("IDA ENVIRONMENT:         %s" % self.config["IDA_ENVIRONMENT"])
        print("IDA CLI ROOT:            %s" % self.cli_root)
        print("IDA HOST:                %s" % self.ida_host)
        print("IDA API:                 %s" % self.ida_api)
        print("TEST DATA DIR:           test%s" % self.token)
        print("TEST PROJECT NAME:       %s" % self.test_project_name)
        print("TEST USER AUTH:          %s" % json.dumps(self.test_user_auth))
        print("ADMIN USER AUTH:         %s" % json.dumps(self.admin_user_auth))
        print("NETRC:                   %s" % self.netrc)
        print("RUN LOCALIZED TESTS:     %s" % self.run_localized_tests)
        print("RUN TRUSTED TESTS:       %s" % self.run_trusted_tests)
        print("CLI CMD:                 %s" % self.cli_cmd)

        if (self.config.get("IDA_ENVIRONMENT", None) == "PRODUCTION") or ("ida.fairdata.fi" in self.ida_host) or ("ida.fairdata.fi" in self.ida_api):
            if self.config.get("RUN_TESTS_IN_PRODUCTION", None) == "I SWEAR I KNOW WHAT I AM DOING AND ACCEPT ALL RESPONSIBILITY":
                print("*** WARNING: Automated tests really shouldn't be run against production! You better know what you are doing!")
                # We never want to run localized tests or trusted tests against production, only tests using user credentials!
                self.run_localized_tests = False
                self.run_trusted_tests = False
                print("RUN LOCALIZED TESTS:     %s" % self.run_localized_tests)
                print("RUN TRUSTED TESTS:       %s" % self.run_trusted_tests)
            else:
                sys.exit("Error: Automated tests should NOT be run against production! Aborting")

        # Clear any residual accounts and test configurations, if they exist from a prior run

        self.success = True
        noflush = self.config["NO_FLUSH_AFTER_TESTS"]
        self.config["NO_FLUSH_AFTER_TESTS"] = "false"
        self.tearDown()
        self.success = False
        self.config["NO_FLUSH_AFTER_TESTS"] = noflush

        # Initialize clean test accounts, if IDA is installed locally

        if self.run_localized_tests:
            cmd = "sudo -u %s %s/tests/utils/initialize-test-accounts" % (self.config["HTTPD_USER"], self.cli_root)
            result = os.system(cmd)
            self.assertEquals(result, 0)

        # Build test ida-config files based on configuration definitions

        Path(self.tempdir).mkdir(parents=True, exist_ok=True)

        f = open("%s/ida-config" % self.tempdir, "w")
        f.write("IDA_HOST=\"%s\"\n" % self.ida_host)
        f.write("IDA_PROJECT=\"%s\"\n" % self.test_project_name)
        f.write("IDA_USERNAME=\"%s\"\n" % self.test_user_name)
        if self.config_source != "HOME":
            f.write("IDA_PASSWORD=\"%s\"\n" % self.test_user_pass)
        f.close()

        f = open("%s/ida-config-invalid-username" % self.tempdir, "w")
        f.write("IDA_HOST=\"%s\"\n" % self.ida_host)
        f.write("IDA_PROJECT=\"%s\"\n" % self.test_project_name)
        f.write("IDA_USERNAME=\"invalid\"\n")
        f.write("IDA_PASSWORD=\"not_used\"\n")
        f.close()

        f = open("%s/ida-config-invalid-password" % self.tempdir, "w")
        f.write("IDA_HOST=\"%s\"\n" % self.ida_host)
        f.write("IDA_PROJECT=\"%s\"\n" % self.test_project_name)
        f.write("IDA_USERNAME=\"%s\"\n" % self.test_user_name)
        f.write("IDA_PASSWORD=\"invalid\"\n")
        f.close()


    def tearDown(self):

        print("(cleaning)")

        if self.run_trusted_tests:

            # Always unlock the service, even if a test failed

            print("Unlock service")
            response = requests.delete("%s/lock/all" % (self.ida_api), auth=self.admin_user_auth, verify=False)
            self.assertEqual(response.status_code, 200, "Failed to unlock service while cleaning up!")

            print("Verify that service is unlocked")
            response = requests.get("%s/lock/all" % (self.ida_api), auth=self.admin_user_auth, verify=False)
            self.assertEqual(response.status_code, 404, "Failed to unlock service while cleaning up!")

        if self.run_localized_tests:

            # Flush all test projects, user accounts, and data, but only if all tests passed,
            # else leave projects and data as-is so test project state can be inspected

            if self.success and self.config.get("NO_FLUSH_AFTER_TESTS", "false") == "false":

                #shutil.rmtree(self.tempdir, ignore_errors=True)

                cmd = "sudo -u %s %s/tests/utils/initialize-test-accounts flush" % (self.config["HTTPD_USER"], self.cli_root)
                result = os.system(cmd)
                self.assertEquals(result, 0)

        self.assertTrue(self.success)


    def waitForPendingActions(self, project, user_auth):
        print("(waiting for pending actions to fully complete)")
        print(".", end='', flush=True)
        response = requests.get("%s/actions?project=%s&status=pending" % (self.ida_api, project), auth=user_auth, verify=False)
        self.assertEqual(response.status_code, 200)
        actions = response.json()
        max_time = time.time() + self.timeout
        while len(actions) > 0 and time.time() < max_time:
            print(".", end='', flush=True)
            time.sleep(1)
            response = requests.get("%s/actions?project=%s&status=pending" % (self.ida_api, project), auth=user_auth, verify=False)
            self.assertEqual(response.status_code, 200)
            actions = response.json()
        print("")
        self.assertEqual(len(actions), 0, "Timed out waiting for pending actions to fully complete")


    def checkForFailedActions(self, project, user_auth):
        print("(verifying no failed actions)")
        response = requests.get("%s/actions?project=%s&status=failed" % (self.ida_api, project), auth=user_auth, verify=False)
        self.assertEqual(response.status_code, 200)
        actions = response.json()
        assert(len(actions) == 0)


    def test_ida_cli(self):

        if not self.run_trusted_tests:
            print("*** WARNING: Trusted account credentials not defined or ignored. A subset of tests will be executed.")

        if not self.run_localized_tests:
            print("*** WARNING: No local IDA installation present. A subset of tests will be executed.")

        print("--- Parameters and Credentials")

        print("Check usage guide output when no parameters provided")
        try:
            output = subprocess.check_output(self.cli_cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("Usage:", output)
        self.assertIn("checksum:", output)

        print("Check usage guide output when -h parameter is provided")
        cmd = "%s -h" % self.cli_cmd
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("Usage:", output)
        self.assertIn("checksum:", output)

        print("Attempt to use invalid action")
        cmd = "%s unknown %s /test%s/Contact.txt %s/Contact.txt" % (self.cli_cmd, self.args, self.token, self.testdata)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: Invalid action", output)
        self.assertTrue(failed, output)

        print("Attempt to use -D parameter with download action")
        cmd = "%s download %s -D /file ./file" % (self.cli_cmd, self.args)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: The -D option is not allowed for the specified action", output)
        self.assertTrue(failed, output)

        print("Attempt to use -D parameter with validate action")
        cmd = "%s validate %s -D /file ./file" % (self.cli_cmd, self.args)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: The -D option is not allowed for the specified action", output)
        self.assertTrue(failed, output)

        print("Attempt to use -D parameter with info action")
        cmd = "%s info %s -D /file" % (self.cli_cmd, self.info_args)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: The -D option is not allowed for the specified action", output)
        self.assertTrue(failed, output)

        print("Attempt to use -D parameter with inventory action")
        cmd = "%s inventory %s -D" % (self.cli_cmd, self.args)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: The -D option is not allowed for the specified action", output)
        self.assertTrue(failed, output)

        print("Attempt to use -F parameter with copy action")
        cmd = "%s copy %s -F /file /file2" % (self.cli_cmd, self.args)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: The -F option is not allowed for the specified action", output)
        self.assertTrue(failed, output)

        print("Attempt to use -F parameter with move action")
        cmd = "%s move %s -F /file /file2" % (self.cli_cmd, self.args)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: The -F option is not allowed for the specified action", output)
        self.assertTrue(failed, output)

        print("Attempt to use -F parameter with delete action")
        cmd = "%s delete %s -F /file" % (self.cli_cmd, self.args)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: The -F option is not allowed for the specified action", output)
        self.assertTrue(failed, output)

        print("Attempt to use -F parameter with download action")
        cmd = "%s download %s -F /file ./file" % (self.cli_cmd, self.args)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: The -F option is not allowed for the specified action", output)
        self.assertTrue(failed, output)

        print("Attempt to use -F parameter with validate action")
        cmd = "%s validate %s -F /file ./file" % (self.cli_cmd, self.args)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: The -F option is not allowed for the specified action", output)
        self.assertTrue(failed, output)

        print("Attempt to use -F parameter with info action")
        cmd = "%s info %s -F /file" % (self.cli_cmd, self.info_args)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: The -F option is not allowed for the specified action", output)
        self.assertTrue(failed, output)

        print("Attempt to use -F parameter with inventory action")
        cmd = "%s inventory %s -F" % (self.cli_cmd, self.args)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: The -F option is not allowed for the specified action", output)
        self.assertTrue(failed, output)

        print("Attempt to use -i parameter with copy action")
        cmd = "%s copy %s -i ./ignore /file /file2" % (self.cli_cmd, self.args)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: The -i option is not allowed for the specified action", output)
        self.assertTrue(failed, output)

        print("Attempt to use -i parameter with move action")
        cmd = "%s move %s -i ./ignore /file /file2" % (self.cli_cmd, self.args)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: The -i option is not allowed for the specified action", output)
        self.assertTrue(failed, output)

        print("Attempt to use -i parameter with delete action")
        cmd = "%s delete %s -i ./ignore /file" % (self.cli_cmd, self.args)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: The -i option is not allowed for the specified action", output)
        self.assertTrue(failed, output)

        print("Attempt to use -i parameter with download action")
        cmd = "%s download %s -i ./ignore /file ./file" % (self.cli_cmd, self.args)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: The -i option is not allowed for the specified action", output)
        self.assertTrue(failed, output)

        print("Attempt to use -i parameter with validate action")
        cmd = "%s validate %s -i ./ignore /file ./file" % (self.cli_cmd, self.args)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: The -i option is not allowed for the specified action", output)
        self.assertTrue(failed, output)

        print("Attempt to use -i parameter with info action")
        cmd = "%s info %s -i ./ignore /file" % (self.cli_cmd, self.info_args)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: The -i option is not allowed for the specified action", output)
        self.assertTrue(failed, output)

        print("Attempt to use -i parameter with inventory action")
        cmd = "%s inventory %s -i ./ignore" % (self.cli_cmd, self.args)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: The -i option is not allowed for the specified action", output)
        self.assertTrue(failed, output)

        print("Attempt to use -f parameter with upload action")
        cmd = "%s upload %s -f /file ./file" % (self.cli_cmd, self.args)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: The -f option is not allowed for the specified action", output)
        self.assertTrue(failed, output)

        print("Attempt to use -f parameter with move action")
        cmd = "%s move %s -f /file /file2" % (self.cli_cmd, self.args)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: The -f option is not allowed for the specified action", output)
        self.assertTrue(failed, output)

        print("Attempt to use -f parameter with delete action")
        cmd = "%s delete %s -f /file" % (self.cli_cmd, self.args)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: The -f option is not allowed for the specified action", output)
        self.assertTrue(failed, output)

        print("Attempt to use -f parameter with inventory action")
        cmd = "%s inventory %s -f" % (self.cli_cmd, self.args)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: The -f option is not allowed for the specified action", output)
        self.assertTrue(failed, output)

        print("Attempt to use -j parameter with upload action")
        cmd = "%s upload %s -j /file ./file" % (self.cli_cmd, self.args)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: The -j option is not allowed for the specified action", output)
        self.assertTrue(failed, output)

        print("Attempt to use -j parameter with copy action")
        cmd = "%s copy %s -j /file /file2" % (self.cli_cmd, self.args)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: The -j option is not allowed for the specified action", output)
        self.assertTrue(failed, output)

        print("Attempt to use -j parameter with move action")
        cmd = "%s move %s -j /file /file2" % (self.cli_cmd, self.args)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: The -j option is not allowed for the specified action", output)
        self.assertTrue(failed, output)

        print("Attempt to use -j parameter with delete action")
        cmd = "%s delete %s -j /file" % (self.cli_cmd, self.args)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: The -j option is not allowed for the specified action", output)
        self.assertTrue(failed, output)

        print("Attempt to use -j parameter with download action")
        cmd = "%s download %s -j /file ./file" % (self.cli_cmd, self.args)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: The -j option is not allowed for the specified action", output)
        self.assertTrue(failed, output)

        print("Attempt to use -j parameter with validate action")
        cmd = "%s validate %s -j /file ./file" % (self.cli_cmd, self.args)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: The -j option is not allowed for the specified action", output)
        self.assertTrue(failed, output)

        print("Attempt to use -j parameter with inventory action")
        cmd = "%s inventory %s -j" % (self.cli_cmd, self.args)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: The -j option is not allowed for the specified action", output)
        self.assertTrue(failed, output)

        print("Attempt to use project name with invalid characters")
        cmd = "%s info %s -p bad@project:name+ /" % (self.cli_cmd, self.info_args)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: Invalid characters in project name", output)
        self.assertTrue(failed, output)

        print("Attempt to upload file to non-existent service")
        cmd = "%s upload %s -t \"http://no.such.service\" /test%s/Contact.txt %s/Contact.txt" % (self.cli_cmd, self.args, self.token, self.testdata)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: Authentication failed", output)
        self.assertTrue(failed, output)

        print("Attempt to upload file to non-existent project")
        cmd = "%s upload %s -p no_such_project /test%s/Contact.txt %s/Contact.txt" % (self.cli_cmd, self.args, self.token, self.testdata)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: Authentication failed", output)
        self.assertTrue(failed, output)

        print("Attempt to upload file using invalid username")
        cmd = "%s upload %s-invalid-username /test%s/Contact.txt %s/Contact.txt" % (self.cli_cmd, self.args, self.token, self.testdata)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: Authentication failed", output)
        self.assertTrue(failed, output)

        print("Attempt to upload file using invalid password")
        cmd = "%s upload %s-invalid-password /test%s/Contact.txt %s/Contact.txt" % (self.cli_cmd, self.args, self.token, self.testdata)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: Authentication failed", output)
        self.assertTrue(failed, output)

        print("Attempt to upload file using unspecified target pathname")
        cmd = "%s upload %s %s/Contact.txt" % (self.cli_cmd, self.args, self.testdata)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: Missing target pathname", output)
        self.assertTrue(failed, output)

        print("Attempt to upload file to pathname exceeding maximum allowed URL encoded pathname length")
        cmd = "%s upload %s /test%s/XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX %s/Contact.txt" % (self.cli_cmd, self.args, self.token, self.testdata)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: URL encoded pathname exceeds maximum allowed length of 200 characters:", output)
        self.assertTrue(failed, output)

        print("Attempt to upload file using unspecified local pathname")
        cmd = "%s upload %s /test%s/Contact.txt" % (self.cli_cmd, self.args, self.token)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: Missing local pathname", output)
        self.assertTrue(failed, output)

        print("Attempt to upload folder using staging root as target pathname")
        cmd = "%s upload %s / %s/2017-08" % (self.cli_cmd, self.args, self.testdata)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: Target pathname invalid or missing", output)
        self.assertTrue(failed, output)

        print("Attempt to upload folder using file system root as local pathname")
        cmd = "%s upload %s /test%s/Data /" % (self.cli_cmd, self.args, self.token)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: Local pathname invalid or missing", output)
        self.assertTrue(failed, output)

        print("Attempt to upload file with missing configuration file pathname")
        cmd = "%s upload %s -c" % (self.cli_cmd, self.args)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: Missing configuration file pathname", output)
        self.assertTrue(failed, output)

        print("Attempt to upload file using non-existent configuration file")
        cmd = "%s upload %s -c /no/such/config/file /test%s/Contact.txt %s/Contact.txt" % (self.cli_cmd, self.args, self.token, self.testdata)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: Can't find specified configuration file", output)
        self.assertTrue(failed, output)

        print("Attempt to upload file with missing ignore file pathname")
        cmd = "%s upload %s -i" % (self.cli_cmd, self.args)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: Missing ignore file pathname", output)
        self.assertTrue(failed, output)

        print("Attempt to upload file using non-existent ignore file")
        cmd = "%s upload %s -i /no/such/ignore/file /test%s/Contact.txt %s/Contact.txt" % (self.cli_cmd, self.args, self.token, self.testdata)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: Can't find specified ignore file", output)
        self.assertTrue(failed, output)

        print("Attempt to upload multiple files to target folder by specifying multiple local pathnames")
        cmd = "%s upload %s /test%s/Legal %s/Contact.txt %s/License.txt" % (self.cli_cmd, self.args, self.token, self.testdata, self.testdata)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: Too many parameters specified", output)
        self.assertTrue(failed, output)

        print("Attempt to delete multiple files by specifying multiple target pathnames")
        cmd = "%s delete %s /test%s/Contact.txt /test%s/License.txt" % (self.cli_cmd, self.args, self.token, self.token)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: Too many parameters specified", output)
        self.assertTrue(failed, output)

        print("--- File Operations")

        print("Upload new file with dry-run parameter and verify no actual upload occurred")
        cmd = "%s upload -D %s /test%s/Contact.txt %s/Contact.txt" % (self.cli_cmd, self.args, self.token, self.testdata)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("* Target uploaded successfully", output)
        self.assertIn("* Uploading file %s/Contact.txt to /%s+/test%s/Contact.txt" % (self.testdata, self.test_project_name, self.token), output)
        if self.run_localized_tests:
            path = Path("%s/test%s/Contact.txt" % (self.staging, self.token))
            self.assertFalse(path.exists(), output)

        print("Upload new file")
        cmd = "%s upload %s /test%s/Contact.txt %s/Contact.txt" % (self.cli_cmd, self.args, self.token, self.testdata)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("Target uploaded successfully", output)
        self.assertIn("Uploading file %s/Contact.txt to /%s+/test%s/Contact.txt" % (self.testdata, self.test_project_name, self.token), output)
        if self.run_localized_tests:
            path = Path("%s/test%s/Contact.txt" % (self.staging, self.token))
            self.assertTrue(path.is_file(), output)
            self.assertEqual(2263, path.stat().st_size, output)

        print("Query IDA for last add data change details and verify change matches last action")
        response = requests.get("%s/dataChanges/%s/last?change=add" % (self.config["IDA_API_ROOT_URL"], self.test_project_name), auth=self.test_user_auth)
        self.assertEqual(response.status_code, 200)
        changeDetails = response.json()
        self.assertIsNotNone(changeDetails)
        self.assertEqual(changeDetails.get('project'), self.test_project_name)
        self.assertEqual(changeDetails.get('user'), self.test_user_name)
        self.assertIsNotNone(changeDetails.get('timestamp'))
        self.assertEqual(changeDetails.get('change'), 'add')
        self.assertEqual(changeDetails.get('pathname'), "/%s+/test%s/Contact.txt" % (self.test_project_name, self.token))
        self.assertIsNone(changeDetails.get('target'))
        self.assertEqual(changeDetails.get('mode'), 'cli')
        timestamp = changeDetails.get('timestamp')
        time.sleep(1)

        print("Validate new file")
        cmd = "%s validate %s /test%s/Contact.txt %s/Contact.txt" % (self.cli_cmd, self.args, self.token, self.testdata)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("FILE_OK: local file %s/Contact.txt matches file in IDA at /%s+/test%s/Contact.txt" % (self.testdata, self.test_project_name, self.token), output)
        self.assertNotIn("WARNING: no checksum reported for file in IDA", output)

        print("Attempt to upload existing file, which will be skipped")
        cmd = "%s upload %s /test%s/Contact.txt %s/Contact.txt" % (self.cli_cmd, self.args, self.token, self.testdata)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("WARNING: one or more files were skipped", output)
        self.assertIn("Skipping existing file %s/Contact.txt at /%s+/test%s/Contact.txt" % (self.testdata, self.test_project_name, self.token), output)
        if self.run_localized_tests:
            path = Path("%s/test%s/Contact.txt" % (self.staging, self.token))
            self.assertTrue(path.is_file(), output)

        print("Force upload of existing file")
        cmd = "%s upload %s -F /test%s/Contact.txt %s/Contact.txt" % (self.cli_cmd, self.args, self.token, self.testdata)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("Target uploaded successfully", output)
        self.assertIn("Uploading file %s/Contact.txt to /%s+/test%s/Contact.txt" % (self.testdata, self.test_project_name, self.token), output)
        if self.run_localized_tests:
            path = Path("%s/test%s/Contact.txt" % (self.staging, self.token))
            self.assertTrue(path.is_file(), output)

        print("Query IDA for last add data change details and verify change matches last action")
        response = requests.get("%s/dataChanges/%s/last?change=add" % (self.config["IDA_API_ROOT_URL"], self.test_project_name), auth=self.test_user_auth)
        self.assertEqual(response.status_code, 200)
        changeDetails = response.json()
        self.assertIsNotNone(changeDetails)
        self.assertEqual(changeDetails.get('project'), self.test_project_name)
        self.assertEqual(changeDetails.get('user'), self.test_user_name)
        self.assertTrue(changeDetails.get('timestamp') > timestamp)
        self.assertEqual(changeDetails.get('change'), 'add')
        self.assertEqual(changeDetails.get('pathname'), "/%s+/test%s/Contact.txt" % (self.test_project_name, self.token))
        self.assertIsNone(changeDetails.get('target'))
        self.assertEqual(changeDetails.get('mode'), 'cli')
        timestamp = changeDetails.get('timestamp')
        time.sleep(1)

        print("Attempt to upload existing file with local file with different file size than in IDA")
        cmd = "%s upload %s /test%s/Contact.txt %s/License.txt" % (self.cli_cmd, self.args, self.token, self.testdata)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("Skipping existing file %s/License.txt at /%s+/test%s/Contact.txt" % (self.testdata, self.test_project_name, self.token), output)
        self.assertIn("WARNING: local file %s/License.txt size 446 does not match IDA file size 2263 at /%s+/test%s/Contact.txt" % (self.testdata, self.test_project_name, self.token), output)
        self.assertIn("WARNING: one or more files were skipped", output)

        print("Force upload existing file with local file with different file size than in IDA")
        cmd = "%s upload %s -F /test%s/Contact.txt %s/License.txt" % (self.cli_cmd, self.args, self.token, self.testdata)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("Target uploaded successfully", output)
        self.assertIn("Uploading file %s/License.txt to /%s+/test%s/Contact.txt" % (self.testdata, self.test_project_name, self.token), output)
        if self.run_localized_tests:
            path = Path("%s/test%s/Contact.txt" % (self.staging, self.token))
            self.assertTrue(path.is_file(), output)
            self.assertEqual(446, path.stat().st_size, output)
            self.assertNotEqual(2263, path.stat().st_size, output)

        print("Validate new file with different local file size than in IDA, which will be reported as invalid")
        cmd = "%s validate %s /test%s/Contact.txt %s/Contact.txt" % (self.cli_cmd, self.args, self.token, self.testdata)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("INVALID: local file %s/Contact.txt size 2263 does not match IDA file size 446 at /%s+/test%s/Contact.txt" % (self.testdata, self.test_project_name, self.token), output)

        print("Validate local file which does not exist in IDA, which will be reported as missing")
        cmd = "%s validate %s /test%s/NoFile.txt %s/Contact.txt" % (self.cli_cmd, self.args, self.token, self.testdata)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("MISSING: local file %s/Contact.txt does not exist in IDA at /%s+/test%s/NoFile.txt" % (self.testdata, self.test_project_name, self.token), output)

        print("Force upload of existing file (to restore correct size)")
        cmd = "%s upload %s -F /test%s/Contact.txt %s/Contact.txt" % (self.cli_cmd, self.args, self.token, self.testdata)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("Target uploaded successfully", output)
        self.assertIn("Uploading file %s/Contact.txt to /%s+/test%s/Contact.txt" % (self.testdata, self.test_project_name, self.token), output)
        if self.run_localized_tests:
            path = Path("%s/test%s/Contact.txt" % (self.staging, self.token))
            self.assertTrue(path.is_file(), output)
            self.assertEqual(2263, path.stat().st_size, output)

        print("Validate restored file")
        cmd = "%s validate %s /test%s/Contact.txt %s/Contact.txt" % (self.cli_cmd, self.args, self.token, self.testdata)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("FILE_OK: local file %s/Contact.txt matches file in IDA at /%s+/test%s/Contact.txt" % (self.testdata, self.test_project_name, self.token), output)

        print("Create variant of file in IDA with same size but modified so that checksum is different")
        cmd = "cat %s/Contact.txt | tr 'a-z' 'A-Z' > /tmp/Contact.txt" % self.testdata
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))

        print("Validate modified local file against same named file in IDA with different checksum, which will be reported as invalid")
        cmd = "%s validate %s /test%s/Contact.txt /tmp/Contact.txt" % (self.cli_cmd, self.args, self.token)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("INVALID: local file /tmp/Contact.txt checksum 04992ff90cd43306900b24abb75da8c40fb583541f4404d94580ac90fc5f9ebc does not match IDA file checksum 8950fc9b4292a82cfd1b5e6bbaec578ed00ac9a9c27bf891130f198fef2f0168 at /%s+/test%s/Contact.txt" % (self.test_project_name, self.token), output)

        print("Upload file to be frozen for checksum tests")
        cmd = "%s upload %s /test%s/f/Contact.txt %s/Contact.txt" % (self.cli_cmd, self.args, self.token, self.testdata)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("Target uploaded successfully", output)
        self.assertIn("Uploading file %s/Contact.txt to /%s+/test%s/f/Contact.txt" % (self.testdata, self.test_project_name, self.token), output)
        if self.run_localized_tests:
            path = Path("%s/test%s/f/Contact.txt" % (self.staging, self.token))
            self.assertTrue(path.is_file(), output)
            self.assertEqual(2263, path.stat().st_size, output)

        print("(freeze file)")
        data = {"project": self.test_project_name, "pathname": "/test%s/f/Contact.txt" % (self.token)}
        response = requests.post("%s/freeze" % self.ida_api, json=data, auth=self.test_user_auth, verify=False)
        self.assertEqual(response.status_code, 200)
        if self.run_localized_tests:
            path = Path("%s/test%s/f/Contact.txt" % (self.frozen, self.token))
            self.assertTrue(path.is_file(), output)
            path = Path("%s/test%s/f/Contact.txt" % (self.staging, self.token))
            self.assertFalse(path.exists(), output)

        self.waitForPendingActions(self.test_project_name, self.test_user_auth)
        self.checkForFailedActions(self.test_project_name, self.test_user_auth)

        print("Validate frozen file")
        cmd = "%s validate %s -f /test%s/f/Contact.txt %s/Contact.txt" % (self.cli_cmd, self.args, self.token, self.testdata)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("FILE_OK: local file %s/Contact.txt matches file in IDA at /%s/test%s/f/Contact.txt" % (self.testdata, self.test_project_name, self.token), output)
        self.assertNotIn("WARNING: no checksum reported for file in IDA", output)

        print("Validate modified local file against same named frozen file in IDA with different checksum, which will be reported as invalid")
        cmd = "%s validate %s -f /test%s/f/Contact.txt /tmp/Contact.txt" % (self.cli_cmd, self.args, self.token)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("INVALID: local file /tmp/Contact.txt checksum 04992ff90cd43306900b24abb75da8c40fb583541f4404d94580ac90fc5f9ebc does not match IDA file checksum 8950fc9b4292a82cfd1b5e6bbaec578ed00ac9a9c27bf891130f198fef2f0168 at /%s/test%s/f/Contact.txt" % (self.test_project_name, self.token), output)

        print("Upload file without upload checksum")
        cmd = "NO_UPLOAD_CHECKSUM=true %s upload %s /test%s/nc/Contact.txt %s/Contact.txt" % (self.cli_cmd, self.args, self.token, self.testdata)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("Target uploaded successfully", output)
        self.assertIn("Uploading file %s/Contact.txt to /%s+/test%s/nc/Contact.txt" % (self.testdata, self.test_project_name, self.token), output)
        if self.run_localized_tests:
            path = Path("%s/test%s/nc/Contact.txt" % (self.staging, self.token))
            self.assertTrue(path.is_file(), output)
            self.assertEqual(2263, path.stat().st_size, output)

        print("Validate file without checksum")
        cmd = "%s validate %s /test%s/nc/Contact.txt %s/Contact.txt" % (self.cli_cmd, self.args, self.token, self.testdata)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("FILE_OK: local file %s/Contact.txt matches file in IDA at /%s+/test%s/nc/Contact.txt" % (self.testdata, self.test_project_name, self.token), output)
        self.assertIn("WARNING: no checksum reported for file in IDA at /%s+/test%s/nc/Contact.txt, validated based on size comparison only" % (self.test_project_name, self.token), output)

        print("Upload file without initial slash in target pathname")
        cmd = "%s upload %s test%s/License.txt %s/License.txt" % (self.cli_cmd, self.args, self.token, self.testdata)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("Target uploaded successfully", output)
        self.assertIn("Uploading file %s/License.txt to /%s+/test%s/License.txt" % (self.testdata, self.test_project_name, self.token), output)
        if self.run_localized_tests:
            path = Path("%s/test%s/License.txt" % (self.staging, self.token))
            self.assertTrue(path.is_file(), output)

        print("Upload file with relative local pathname")
        cmd = "cd %s/2017-08; %s upload %s /test%s/License2.txt ../License.txt" % (self.testdata, self.cli_cmd, self.args, self.token)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("Target uploaded successfully", output)
        if self.run_localized_tests:
            path = Path("%s/test%s/License2.txt" % (self.staging, self.token))
            self.assertTrue(path.is_file(), output)

        print("Upload zero size file")
        cmd = "%s upload %s /test%s/zero_size_file %s/2017-08/Experiment_1/zero_size_file" % (self.cli_cmd, self.args, self.token, self.testdata)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("Target uploaded successfully", output)
        if self.run_localized_tests:
            path = Path("%s/test%s/zero_size_file" % (self.staging, self.token))
            self.assertTrue(path.is_file(), output)
            self.assertEquals(0, path.stat().st_size, output)

        print("Query IDA for last add data change details and verify change matches last action")
        response = requests.get("%s/dataChanges/%s/last?change=add" % (self.config["IDA_API_ROOT_URL"], self.test_project_name), auth=self.test_user_auth)
        self.assertEqual(response.status_code, 200)
        changeDetails = response.json()
        self.assertIsNotNone(changeDetails)
        self.assertEqual(changeDetails.get('project'), self.test_project_name)
        self.assertEqual(changeDetails.get('user'), self.test_user_name)
        self.assertTrue(changeDetails.get('timestamp') > timestamp)
        self.assertEqual(changeDetails.get('change'), 'add')
        self.assertEqual(changeDetails.get('pathname'), "/%s+/test%s/zero_size_file" % (self.test_project_name, self.token))
        self.assertIsNone(changeDetails.get('target'))
        self.assertEqual(changeDetails.get('mode'), 'cli')
        timestamp = changeDetails.get('timestamp')
        time.sleep(1)

        print("Copy file within staging with dry-run parameter and verify no actual copy occurred")
        cmd = "%s copy %s -D /test%s/Contact.txt /test%s/a/b/c/Contact.txt" % (self.cli_cmd, self.args, self.token, self.token)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("* Target copied successfully", output)
        if self.run_localized_tests:
            path = Path("%s/test%s/a/b/c/Contact.txt" % (self.staging, self.token))
            self.assertFalse(path.exists(), output)

        print("Copy file within staging")
        cmd = "%s copy %s /test%s/Contact.txt /test%s/a/b/c/Contact.txt" % (self.cli_cmd, self.args, self.token, self.token)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("Target copied successfully", output)
        if self.run_localized_tests:
            path = Path("%s/test%s/Contact.txt" % (self.staging, self.token))
            self.assertTrue(path.is_file(), output)
            path = Path("%s/test%s/a/b/c/Contact.txt" % (self.staging, self.token))
            self.assertTrue(path.is_file(), output)

        print("Query IDA for last copy data change details and verify change matches last action")
        response = requests.get("%s/dataChanges/%s/last?change=copy" % (self.config["IDA_API_ROOT_URL"], self.test_project_name), auth=self.test_user_auth)
        self.assertEqual(response.status_code, 200)
        changeDetails = response.json()
        self.assertIsNotNone(changeDetails)
        self.assertEqual(changeDetails.get('project'), self.test_project_name)
        self.assertEqual(changeDetails.get('user'), self.test_user_name)
        self.assertTrue(changeDetails.get('timestamp') > timestamp)
        self.assertEqual(changeDetails.get('change'), 'copy')
        self.assertEqual(changeDetails.get('pathname'), "/%s+/test%s/Contact.txt" % (self.test_project_name, self.token))
        self.assertEqual(changeDetails.get('target'), "/%s+/test%s/a/b/c/Contact.txt" % (self.test_project_name, self.token))
        self.assertEqual(changeDetails.get('mode'), 'cli')
        timestamp = changeDetails.get('timestamp')
        time.sleep(1)

        print("(freeze file)")
        data = {"project": self.test_project_name, "pathname": "/test%s/a/b/c/Contact.txt" % (self.token)}
        response = requests.post("%s/freeze" % self.ida_api, json=data, auth=self.test_user_auth, verify=False)
        self.assertEqual(response.status_code, 200)
        if self.run_localized_tests:
            path = Path("%s/test%s/a/b/c/Contact.txt" % (self.frozen, self.token))
            self.assertTrue(path.is_file(), output)
            path = Path("%s/test%s/a/b/c/Contact.txt" % (self.staging, self.token))
            self.assertFalse(path.exists(), output)

        self.waitForPendingActions(self.test_project_name, self.test_user_auth)
        self.checkForFailedActions(self.test_project_name, self.test_user_auth)

        print("Copy file from frozen area to staging area with dry-run parameter and verify no actual copy occurred")
        cmd = "%s copy %s -f -D /test%s/a/b/c/Contact.txt /test%s/a/b/c/Contact.txt" % (self.cli_cmd, self.args, self.token, self.token)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("* Target copied successfully", output)
        if self.run_localized_tests:
            path = Path("%s/test%s/a/b/c/Contact.txt" % (self.frozen, self.token))
            self.assertTrue(path.is_file(), output)
            path = Path("%s/test%s/a/b/c/Contact.txt" % (self.staging, self.token))
            self.assertFalse(path.exists(), output)

        print("Copy file from frozen area to staging area")
        cmd = "%s copy %s -f /test%s/a/b/c/Contact.txt /test%s/a/b/c/Contact.txt" % (self.cli_cmd, self.args, self.token, self.token)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("Target copied successfully", output)
        if self.run_localized_tests:
            path = Path("%s/test%s/a/b/c/Contact.txt" % (self.frozen, self.token))
            self.assertTrue(path.is_file(), output)
            path = Path("%s/test%s/a/b/c/Contact.txt" % (self.staging, self.token))
            self.assertTrue(path.is_file(), output)

        print("Query IDA for last copy data change details and verify change matches last action")
        response = requests.get("%s/dataChanges/%s/last?change=copy" % (self.config["IDA_API_ROOT_URL"], self.test_project_name), auth=self.test_user_auth)
        self.assertEqual(response.status_code, 200)
        changeDetails = response.json()
        self.assertIsNotNone(changeDetails)
        self.assertEqual(changeDetails.get('project'), self.test_project_name)
        self.assertEqual(changeDetails.get('user'), self.test_user_name)
        self.assertTrue(changeDetails.get('timestamp') > timestamp)
        self.assertEqual(changeDetails.get('change'), 'copy')
        self.assertEqual(changeDetails.get('pathname'), "/%s/test%s/a/b/c/Contact.txt" % (self.test_project_name, self.token))
        self.assertEqual(changeDetails.get('target'), "/%s+/test%s/a/b/c/Contact.txt" % (self.test_project_name, self.token))
        self.assertEqual(changeDetails.get('mode'), 'cli')
        timestamp = changeDetails.get('timestamp')
        time.sleep(1)

        print("Copy zero size file")
        cmd = "%s copy %s /test%s/zero_size_file /test%s/a/b/c/zero_size_file" % (self.cli_cmd, self.args, self.token, self.token)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("Target copied successfully", output)
        if self.run_localized_tests:
            path = Path("%s/test%s/zero_size_file" % (self.staging, self.token))
            self.assertTrue(path.is_file(), output)
            self.assertEquals(0, path.stat().st_size, output)
            path = Path("%s/test%s/a/b/c/zero_size_file" % (self.staging, self.token))
            self.assertTrue(path.is_file(), output)
            self.assertEquals(0, path.stat().st_size, output)

        print("Query IDA for last copy data change details and verify change matches last action")
        response = requests.get("%s/dataChanges/%s/last?change=copy" % (self.config["IDA_API_ROOT_URL"], self.test_project_name), auth=self.test_user_auth)
        self.assertEqual(response.status_code, 200)
        changeDetails = response.json()
        self.assertIsNotNone(changeDetails)
        self.assertEqual(changeDetails.get('project'), self.test_project_name)
        self.assertEqual(changeDetails.get('user'), self.test_user_name)
        self.assertTrue(changeDetails.get('timestamp') > timestamp)
        self.assertEqual(changeDetails.get('change'), 'copy')
        self.assertEqual(changeDetails.get('pathname'), "/%s+/test%s/zero_size_file" % (self.test_project_name, self.token))
        self.assertEqual(changeDetails.get('target'), "/%s+/test%s/a/b/c/zero_size_file" % (self.test_project_name, self.token))
        self.assertEqual(changeDetails.get('mode'), 'cli')
        timestamp = changeDetails.get('timestamp')
        time.sleep(1)

        print("Rename with dry-run parameter and verify no actual renaming occurred")
        cmd = "%s move %s -D /test%s/Contact.txt /test%s/Contact2.txt" % (self.cli_cmd, self.args, self.token, self.token)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("* Target moved successfully", output)
        if self.run_localized_tests:
            path = Path("%s/test%s/Contact.txt" % (self.staging, self.token))
            self.assertTrue(path.is_file(), output)
            path = Path("%s/test%s/Contact2.txt" % (self.staging, self.token))
            self.assertFalse(path.exists(), output)

        print("Rename file")
        cmd = "%s move %s /test%s/Contact.txt /test%s/Contact2.txt" % (self.cli_cmd, self.args, self.token, self.token)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("Target moved successfully", output)
        if self.run_localized_tests:
            path = Path("%s/test%s/Contact.txt" % (self.staging, self.token))
            self.assertFalse(path.exists(), output)
            path = Path("%s/test%s/Contact2.txt" % (self.staging, self.token))
            self.assertTrue(path.is_file(), output)

        print("Query IDA for last rename data change details and verify change matches last action")
        response = requests.get("%s/dataChanges/%s/last?change=rename" % (self.config["IDA_API_ROOT_URL"], self.test_project_name), auth=self.test_user_auth)
        self.assertEqual(response.status_code, 200)
        changeDetails = response.json()
        self.assertIsNotNone(changeDetails)
        self.assertEqual(changeDetails.get('project'), self.test_project_name)
        self.assertEqual(changeDetails.get('user'), self.test_user_name)
        self.assertTrue(changeDetails.get('timestamp') > timestamp)
        self.assertEqual(changeDetails.get('change'), 'rename')
        self.assertEqual(changeDetails.get('pathname'), "/%s+/test%s/Contact.txt" % (self.test_project_name, self.token))
        self.assertEqual(changeDetails.get('target'), "/%s+/test%s/Contact2.txt" % (self.test_project_name, self.token))
        self.assertEqual(changeDetails.get('mode'), 'cli')
        timestamp = changeDetails.get('timestamp')
        time.sleep(1)

        print("Move with dry-run parameter and verify no actual move occurred")
        cmd = "%s move %s -D /test%s/Contact2.txt /test%s/x/y/z/Contact.txt" % (self.cli_cmd, self.args, self.token, self.token)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("Target moved successfully", output)
        if self.run_localized_tests:
            path = Path("%s/test%s/Contact2.txt" % (self.staging, self.token))
            self.assertTrue(path.is_file(), output)
            path = Path("%s/test%s/x/y/z/Contact.txt" % (self.staging, self.token))
            self.assertFalse(path.exists(), output)

        print("Move file")
        cmd = "%s move %s /test%s/Contact2.txt /test%s/x/y/z/Contact.txt" % (self.cli_cmd, self.args, self.token, self.token)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("Target moved successfully", output)
        if self.run_localized_tests:
            path = Path("%s/test%s/Contact2.txt" % (self.staging, self.token))
            self.assertFalse(path.exists(), output)
            path = Path("%s/test%s/x/y/z/Contact.txt" % (self.staging, self.token))
            self.assertTrue(path.is_file(), output)

        print("Query IDA for last move data change details and verify change matches last action")
        response = requests.get("%s/dataChanges/%s/last?change=move" % (self.config["IDA_API_ROOT_URL"], self.test_project_name), auth=self.test_user_auth)
        self.assertEqual(response.status_code, 200)
        changeDetails = response.json()
        self.assertIsNotNone(changeDetails)
        self.assertEqual(changeDetails.get('project'), self.test_project_name)
        self.assertEqual(changeDetails.get('user'), self.test_user_name)
        self.assertTrue(changeDetails.get('timestamp') > timestamp)
        self.assertEqual(changeDetails.get('change'), 'move')
        self.assertEqual(changeDetails.get('pathname'), "/%s+/test%s/Contact2.txt" % (self.test_project_name, self.token))
        self.assertEqual(changeDetails.get('target'), "/%s+/test%s/x/y/z/Contact.txt" % (self.test_project_name, self.token))
        self.assertEqual(changeDetails.get('mode'), 'cli')
        timestamp = changeDetails.get('timestamp')
        time.sleep(1)

        print("Download file")
        cmd = "%s download %s /test%s/x/y/z/Contact.txt %s/a/b/c/Contact.txt" % (self.cli_cmd, self.args, self.token, self.tempdir)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("Target downloaded successfully", output)
        path = Path("%s/a/b/c/Contact.txt" % (self.tempdir))
        self.assertTrue(path.is_file(), output)
        self.assertEquals(2263, path.stat().st_size, output)

        print("Attempt to upload file using invalid local pathname")
        cmd = "%s upload %s /test%s/no/such/file.txt /no/such/file.txt" % (self.cli_cmd, self.args, self.token)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: Can't find specified file or directory", output)
        self.assertTrue(failed, output)

        print("Attempt to copy file to existing target pathname")
        cmd = "%s copy %s /test%s/License2.txt /test%s/x/y/z/Contact.txt" % (self.cli_cmd, self.args, self.token, self.token)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: Specified new target already exists", output)
        self.assertTrue(failed, output)

        print("Attempt to move file to existing target pathname")
        cmd = "%s move %s /test%s/License2.txt /test%s/x/y/z/Contact.txt" % (self.cli_cmd, self.args, self.token, self.token)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: Specified new target already exists", output)
        self.assertTrue(failed, output)

        print("Attempt to upload file to frozen area")
        cmd = "%s upload %s -f /test%s/LicenseX.txt %s/License.txt" % (self.cli_cmd, self.args, self.token, self.testdata)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: The -f option is not allowed for the specified action", output)
        self.assertTrue(failed, output)

        print("Attempt to move frozen file")
        cmd = "%s move %s -f /test%s/License.txt /test%s/LicenseX.txt" % (self.cli_cmd, self.args, self.token, self.token)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: The -f option is not allowed for the specified action", output)
        self.assertTrue(failed, output)

        print("Attempt to delete frozen file")
        cmd = "%s delete %s -f /test%s/License.txt" % (self.cli_cmd, self.args, self.token)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: The -f option is not allowed for the specified action", output)
        self.assertTrue(failed, output)

        print("Attempt to download file using invalid target pathname")
        cmd = "%s download %s /test%s/no/such/file.txt %s/no/such/file.txt" % (self.cli_cmd, self.args, self.token, self.tempdir)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: Specified target not found", output)
        self.assertTrue(failed, output)

        print("Attempt to download file using local pathname of existing file")
        cmd = "%s download %s /test%s/x/y/z/Contact.txt %s/a/b/c/Contact.txt" % (self.cli_cmd, self.args, self.token, self.tempdir)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: Specified local pathname already exists", output)
        self.assertTrue(failed, output)

        print("Delete file with dry-run parameter and verify no actual deletion occurred")
        cmd = "%s delete %s -D /test%s/x/y/z/Contact.txt" % (self.cli_cmd, self.args, self.token)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("* Target deleted successfully", output)
        if self.run_localized_tests:
            path = Path("%s/test%s/x/y/z/Contact.txt" % (self.staging, self.token))
            self.assertTrue(path.is_file(), output)

        print("Delete file")
        cmd = "%s delete %s /test%s/x/y/z/Contact.txt" % (self.cli_cmd, self.args, self.token)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("Target deleted successfully", output)
        if self.run_localized_tests:
            path = Path("%s/test%s/x/y/z/Contact.txt" % (self.staging, self.token))
            self.assertFalse(path.exists(), output)

        print("Query IDA for last delete data change details and verify change matches last action")
        response = requests.get("%s/dataChanges/%s/last?change=delete" % (self.config["IDA_API_ROOT_URL"], self.test_project_name), auth=self.test_user_auth)
        self.assertEqual(response.status_code, 200)
        changeDetails = response.json()
        self.assertIsNotNone(changeDetails)
        self.assertEqual(changeDetails.get('project'), self.test_project_name)
        self.assertEqual(changeDetails.get('user'), self.test_user_name)
        self.assertTrue(changeDetails.get('timestamp') > timestamp)
        self.assertEqual(changeDetails.get('change'), 'delete')
        self.assertEqual(changeDetails.get('pathname'), "/%s+/test%s/x/y/z/Contact.txt" % (self.test_project_name, self.token))
        self.assertIsNone(changeDetails.get('target'))
        self.assertEqual(changeDetails.get('mode'), 'cli')
        timestamp = changeDetails.get('timestamp')
        time.sleep(1)

        print("--- Folder Operations")

        print("Upload new folder with dry-run parameter and verify no actual upload occurred")
        cmd = "%s upload %s -D /test%s/2017-08/Experiment_1 %s/2017-08/Experiment_1" % (self.cli_cmd, self.args, self.token, self.testdata)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("* Target uploaded successfully", output)
        if self.run_localized_tests:
            path = Path("%s/test%s/2017-08/Experiment_1/baseline" % (self.staging, self.token))
            self.assertFalse(path.exists(), output)

        print("Upload new folder")
        cmd = "%s upload %s /test%s/2017-08/Experiment_1 %s/2017-08/Experiment_1" % (self.cli_cmd, self.args, self.token, self.testdata)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("Target uploaded successfully", output)
        if self.run_localized_tests:
            path = Path("%s/test%s/2017-08/Experiment_1/baseline" % (self.staging, self.token))
            self.assertTrue(path.is_dir(), output)
            path = Path("%s/test%s/2017-08/Experiment_1/baseline/test01.dat" % (self.staging, self.token))
            self.assertTrue(path.is_file(), output)
            self.assertEquals(446, path.stat().st_size, output)
            path = Path("%s/test%s/2017-08/Experiment_1/baseline/test02.dat" % (self.staging, self.token))
            self.assertTrue(path.is_file(), output)
            self.assertEquals(1531, path.stat().st_size, output)
            path = Path("%s/test%s/2017-08/Experiment_1/baseline/test03.dat" % (self.staging, self.token))
            self.assertTrue(path.is_file(), output)
            self.assertEquals(2263, path.stat().st_size, output)
            path = Path("%s/test%s/2017-08/Experiment_1/baseline/test04.dat" % (self.staging, self.token))
            self.assertTrue(path.is_file(), output)
            self.assertEquals(3329, path.stat().st_size, output)
            path = Path("%s/test%s/2017-08/Experiment_1/baseline/test05.dat" % (self.staging, self.token))
            self.assertTrue(path.is_file(), output)
            self.assertEquals(3728, path.stat().st_size, output)

        print("Query IDA for last add data change details and verify change matches last action")
        response = requests.get("%s/dataChanges/%s/last?change=add" % (self.config["IDA_API_ROOT_URL"], self.test_project_name), auth=self.test_user_auth)
        self.assertEqual(response.status_code, 200)
        changeDetails = response.json()
        self.assertIsNotNone(changeDetails)
        self.assertEqual(changeDetails.get('project'), self.test_project_name)
        self.assertEqual(changeDetails.get('user'), self.test_user_name)
        self.assertTrue(changeDetails.get('timestamp') > timestamp)
        self.assertEqual(changeDetails.get('change'), 'add')
        self.assertTrue(changeDetails.get('pathname').startswith("/%s+/test%s/2017-08/Experiment_1" % (self.test_project_name, self.token)))
        self.assertIsNone(changeDetails.get('target'))
        self.assertEqual(changeDetails.get('mode'), 'cli')
        timestamp = changeDetails.get('timestamp')
        time.sleep(1)

        print("Upload additional files to existing folder")
        cmd = "%s upload %s /test%s/2017-08/Experiment_1/baseline2 %s/2017-08/Experiment_2/baseline" % (self.cli_cmd, self.args, self.token, self.testdata)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("Target uploaded successfully", output)
        if self.run_localized_tests:
            path = Path("%s/test%s/2017-08/Experiment_1/baseline2" % (self.staging, self.token))
            self.assertTrue(path.is_dir(), output)
            path = Path("%s/test%s/2017-08/Experiment_1/baseline2/test01.dat" % (self.staging, self.token))
            self.assertTrue(path.is_file(), output)
            self.assertEquals(446, path.stat().st_size, output)

        print("Upload folder without initial slash in target pathname")
        cmd = "%s upload %s test%s/2017-08/Experiment_1/baseline3 %s/2017-08/Experiment_2/baseline" % (self.cli_cmd, self.args, self.token, self.testdata)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("Target uploaded successfully", output)
        if self.run_localized_tests:
            path = Path("%s/test%s/2017-08/Experiment_1/baseline3" % (self.staging, self.token))
            self.assertTrue(path.is_dir(), output)
            path = Path("%s/test%s/2017-08/Experiment_1/baseline3/test01.dat" % (self.staging, self.token))
            self.assertTrue(path.is_file(), output)
            self.assertEquals(446, path.stat().st_size, output)

        print("Upload folder with trailing slash in target pathname")
        cmd = "%s upload %s /test%s/2017-08/Experiment_1/baseline4/ %s/2017-08/Experiment_2/baseline" % (self.cli_cmd, self.args, self.token, self.testdata)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("Target uploaded successfully", output)
        if self.run_localized_tests:
            path = Path("%s/test%s/2017-08/Experiment_1/baseline4" % (self.staging, self.token))
            self.assertTrue(path.is_dir(), output)
            path = Path("%s/test%s/2017-08/Experiment_1/baseline4/test01.dat" % (self.staging, self.token))
            self.assertTrue(path.is_file(), output)
            self.assertEquals(446, path.stat().st_size, output)

        print("Upload folder with trailing slash in local pathname")
        cmd = "%s upload %s /test%s/2017-08/Experiment_1/baseline5 %s/2017-08/Experiment_2/baseline/" % (self.cli_cmd, self.args, self.token, self.testdata)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("Target uploaded successfully", output)
        if self.run_localized_tests:
            path = Path("%s/test%s/2017-08/Experiment_1/baseline5" % (self.staging, self.token))
            self.assertTrue(path.is_dir(), output)
            path = Path("%s/test%s/2017-08/Experiment_1/baseline5/test01.dat" % (self.staging, self.token))
            self.assertTrue(path.is_file(), output)
            self.assertEquals(446, path.stat().st_size, output)

        print("Upload folder with relative local pathname")
        cmd = "cd %s/2017-08/Experiment_2; %s upload %s /test%s/2017-08/Experiment_1/baseline6 ./baseline" % (self.testdata, self.cli_cmd, self.args, self.token)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("Target uploaded successfully", output)
        if self.run_localized_tests:
            path = Path("%s/test%s/2017-08/Experiment_1/baseline6" % (self.staging, self.token))
            self.assertTrue(path.is_dir(), output)
            path = Path("%s/test%s/2017-08/Experiment_1/baseline6/test01.dat" % (self.staging, self.token))
            self.assertTrue(path.is_file(), output)
            self.assertEquals(446, path.stat().st_size, output)

        print("Upload folder with ignore patterns")
        cmd = "%s upload %s %s /test%s/2017-10 %s/2017-10" % (self.cli_cmd, self.args, self.ignore_file, self.token, self.testdata)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("Target uploaded successfully", output)
        if self.run_localized_tests:
            path = Path("%s/test%s/2017-10/Experiment_3/baseline" % (self.staging, self.token))
            self.assertTrue(path.is_dir(), output)
            path = Path("%s/test%s/2017-10/Experiment_3/baseline/test01.dat" % (self.staging, self.token))
            self.assertTrue(path.is_file(), output)
            self.assertEquals(446, path.stat().st_size, output)
            path = Path("%s/test%s/2017-10/.DS_Store" % (self.staging, self.token))
            self.assertFalse(path.exists(), output)
            path = Path("%s/test%s/2017-10/Experiment_3/test05.dat" % (self.staging, self.token))
            self.assertFalse(path.exists(), output)
            path = Path("%s/test%s/2017-10/Experiment_3/baseline/test05.dat" % (self.staging, self.token))
            self.assertFalse(path.exists(), output)
            path = Path("%s/test%s/2017-10/.hidden_folder" % (self.staging, self.token))
            self.assertTrue(path.exists(), output)
            path = Path("%s/test%s/2017-10/.hidden_folder/test.dat" % (self.staging, self.token))
            self.assertTrue(path.exists(), output)
            path = Path("%s/test%s/2017-10/Experiment_3/.hidden_file" % (self.staging, self.token))
            self.assertFalse(path.exists(), output)

        print("Upload folder with files containing special characters")
        cmd = "%s upload %s /test%s/Special\ Characters %s/Special\ Characters" % (self.cli_cmd, self.args, self.token, self.testdata)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("Target uploaded successfully", output)
        if self.run_localized_tests:
            path = Path("%s/test%s/Special Characters" % (self.staging, self.token))
            self.assertTrue(path.is_dir(), output)
            path = Path("%s/test%s/Special Characters/file_with_ä_and_ö_and_even_å_oh_my.dat" % (self.staging, self.token))
            self.assertTrue(path.is_file(), output)
            self.assertEquals(446, path.stat().st_size, output)
            path = Path("%s/test%s/Special Characters/file with spaces and (various) [brackets] {etc}" % (self.staging, self.token))
            self.assertTrue(path.is_file(), output)
            self.assertEquals(446, path.stat().st_size, output)
            path = Path("%s/test%s/Special Characters/$file with special characters #~;@-+'&!%%^.dat" % (self.staging, self.token))
            self.assertTrue(path.is_file(), output)
            self.assertEquals(446, path.stat().st_size, output)

        print("Copy folder within staging area with dry-run parameter and verify no actual copy occurred")
        cmd = "%s copy %s -D /test%s/2017-10/Experiment_3/baseline /test%s/2017-11/Experiment_8/baseline" % (self.cli_cmd, self.args, self.token, self.token)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("* Target copied successfully", output)
        if self.run_localized_tests:
            path = Path("%s/test%s/2017-11/Experiment_8/baseline" % (self.staging, self.token))
            self.assertFalse(path.exists(), output)

        print("Copy folder within staging area")
        cmd = "%s copy %s /test%s/2017-10/Experiment_3/baseline /test%s/2017-11/Experiment_8/baseline" % (self.cli_cmd, self.args, self.token, self.token)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("Target copied successfully", output)
        if self.run_localized_tests:
            path = Path("%s/test%s/2017-10/Experiment_3/baseline" % (self.staging, self.token))
            self.assertTrue(path.is_dir(), output)
            path = Path("%s/test%s/2017-10/Experiment_3/baseline/zero_size_file" % (self.staging, self.token))
            self.assertTrue(path.is_file(), output)
            self.assertEquals(0, path.stat().st_size, output)
            path = Path("%s/test%s/2017-11/Experiment_8/baseline" % (self.staging, self.token))
            self.assertTrue(path.is_dir(), output)
            path = Path("%s/test%s/2017-11/Experiment_8/baseline/zero_size_file" % (self.staging, self.token))
            self.assertTrue(path.is_file(), output)
            self.assertEquals(0, path.stat().st_size, output)

        print("Query IDA for last copy data change details and verify change matches last action")
        response = requests.get("%s/dataChanges/%s/last?change=copy" % (self.config["IDA_API_ROOT_URL"], self.test_project_name), auth=self.test_user_auth)
        self.assertEqual(response.status_code, 200)
        changeDetails = response.json()
        self.assertIsNotNone(changeDetails)
        self.assertEqual(changeDetails.get('project'), self.test_project_name)
        self.assertEqual(changeDetails.get('user'), self.test_user_name)
        self.assertTrue(changeDetails.get('timestamp') > timestamp)
        self.assertEqual(changeDetails.get('change'), 'copy')
        self.assertEqual(changeDetails.get('pathname'), "/%s+/test%s/2017-10/Experiment_3/baseline" % (self.test_project_name, self.token))
        self.assertEqual(changeDetails.get('target'), "/%s+/test%s/2017-11/Experiment_8/baseline" % (self.test_project_name, self.token))
        self.assertEqual(changeDetails.get('mode'), 'cli')
        timestamp = changeDetails.get('timestamp')
        time.sleep(1)

        print("(freeze folder)")
        data = {"project": self.test_project_name, "pathname": "/test%s/2017-11/Experiment_8" % (self.token)}
        response = requests.post("%s/freeze" % self.ida_api, json=data, auth=self.test_user_auth, verify=False)
        self.assertEqual(response.status_code, 200)
        if self.run_localized_tests:
            path = Path("%s/test%s/2017-11/Experiment_8" % (self.frozen, self.token))
            self.assertTrue(path.is_dir(), output)
            path = Path("%s/test%s/2017-11/Experiment_8" % (self.staging, self.token))
            self.assertFalse(path.exists(), output)

        self.waitForPendingActions(self.test_project_name, self.test_user_auth)
        self.checkForFailedActions(self.test_project_name, self.test_user_auth)

        print("Copy folder from frozen area to staging area")
        cmd = "%s copy %s -f /test%s/2017-11/Experiment_8/baseline /test%s/2017-11/Experiment_8/baseline" % (self.cli_cmd, self.args, self.token, self.token)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("Target copied successfully", output)
        if self.run_localized_tests:
            path = Path("%s/test%s/2017-11/Experiment_8/baseline" % (self.frozen, self.token))
            self.assertTrue(path.is_dir(), output)
            path = Path("%s/test%s/2017-11/Experiment_8/baseline/zero_size_file" % (self.frozen, self.token))
            self.assertTrue(path.is_file(), output)
            self.assertEquals(0, path.stat().st_size, output)
            path = Path("%s/test%s/2017-11/Experiment_8/baseline" % (self.staging, self.token))
            self.assertTrue(path.is_dir(), output)
            path = Path("%s/test%s/2017-11/Experiment_8/baseline/zero_size_file" % (self.staging, self.token))
            self.assertTrue(path.is_file(), output)
            self.assertEquals(0, path.stat().st_size, output)

        print("Query IDA for last copy data change details and verify change matches last action")
        response = requests.get("%s/dataChanges/%s/last?change=copy" % (self.config["IDA_API_ROOT_URL"], self.test_project_name), auth=self.test_user_auth)
        self.assertEqual(response.status_code, 200)
        changeDetails = response.json()
        self.assertIsNotNone(changeDetails)
        self.assertEqual(changeDetails.get('project'), self.test_project_name)
        self.assertEqual(changeDetails.get('user'), self.test_user_name)
        self.assertTrue(changeDetails.get('timestamp') > timestamp)
        self.assertEqual(changeDetails.get('change'), 'copy')
        self.assertEqual(changeDetails.get('pathname'), "/%s/test%s/2017-11/Experiment_8/baseline" % (self.test_project_name, self.token))
        self.assertEqual(changeDetails.get('target'), "/%s+/test%s/2017-11/Experiment_8/baseline" % (self.test_project_name, self.token))
        self.assertEqual(changeDetails.get('mode'), 'cli')
        timestamp = changeDetails.get('timestamp')
        time.sleep(1)

        print("Rename folder within staging with dry-run parameter and verify no actual renaming occurred")
        cmd = "%s move %s -D /test%s/2017-10/Experiment_3/baseline /test%s/2017-10/Experiment_3/baseline_old" % (self.cli_cmd, self.args, self.token, self.token)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("* Target moved successfully", output)
        if self.run_localized_tests:
            path = Path("%s/test%s/2017-10/Experiment_3/baseline" % (self.staging, self.token))
            self.assertTrue(path.is_dir(), output)
            path = Path("%s/test%s/2017-10/Experiment_3/baseline_old" % (self.staging, self.token))
            self.assertFalse(path.exists(), output)

        print("Rename folder")
        cmd = "%s move %s /test%s/2017-10/Experiment_3/baseline /test%s/2017-10/Experiment_3/baseline_old" % (self.cli_cmd, self.args, self.token, self.token)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("Target moved successfully", output)
        if self.run_localized_tests:
            path = Path("%s/test%s/2017-10/Experiment_3/baseline" % (self.staging, self.token))
            self.assertFalse(path.exists(), output)
            path = Path("%s/test%s/2017-10/Experiment_3/baseline_old" % (self.staging, self.token))
            self.assertTrue(path.is_dir(), output)

        print("Query IDA for last rename data change details and verify change matches last action")
        response = requests.get("%s/dataChanges/%s/last?change=rename" % (self.config["IDA_API_ROOT_URL"], self.test_project_name), auth=self.test_user_auth)
        self.assertEqual(response.status_code, 200)
        changeDetails = response.json()
        self.assertIsNotNone(changeDetails)
        self.assertEqual(changeDetails.get('project'), self.test_project_name)
        self.assertEqual(changeDetails.get('user'), self.test_user_name)
        self.assertTrue(changeDetails.get('timestamp') > timestamp)
        self.assertEqual(changeDetails.get('change'), 'rename')
        self.assertEqual(changeDetails.get('pathname'), "/%s+/test%s/2017-10/Experiment_3/baseline" % (self.test_project_name, self.token))
        self.assertEqual(changeDetails.get('target'), "/%s+/test%s/2017-10/Experiment_3/baseline_old" % (self.test_project_name, self.token))
        self.assertEqual(changeDetails.get('mode'), 'cli')
        timestamp = changeDetails.get('timestamp')
        time.sleep(1)

        print("Move folder within staging with dry-run parameter and verify no actual move occurred")
        cmd = "%s move %s -D /test%s/2017-10/Experiment_3/baseline_old /test%s/2017-11/Experiment_9/baseline_x" % (self.cli_cmd, self.args, self.token, self.token)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("Target moved successfully", output)
        if self.run_localized_tests:
            path = Path("%s/test%s/2017-10/Experiment_3/baseline_old" % (self.staging, self.token))
            self.assertTrue(path.is_dir(), output)
            path = Path("%s/test%s/2017-11/Experiment_9/baseline_x" % (self.staging, self.token))
            self.assertFalse(path.exists(), output)

        print("Move folder")
        cmd = "%s move %s /test%s/2017-10/Experiment_3/baseline_old /test%s/2017-11/Experiment_9/baseline_x" % (self.cli_cmd, self.args, self.token, self.token)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("Target moved successfully", output)
        if self.run_localized_tests:
            path = Path("%s/test%s/2017-10/Experiment_3/baseline_old" % (self.staging, self.token))
            self.assertFalse(path.exists(), output)
            path = Path("%s/test%s/2017-11/Experiment_9/baseline_x" % (self.staging, self.token))
            self.assertTrue(path.is_dir(), output)
            path = Path("%s/test%s/2017-11/Experiment_9/baseline_x/zero_size_file" % (self.staging, self.token))
            self.assertTrue(path.is_file(), output)
            self.assertEquals(0, path.stat().st_size, output)

        print("Query IDA for last move data change details and verify change matches last action")
        response = requests.get("%s/dataChanges/%s/last?change=move" % (self.config["IDA_API_ROOT_URL"], self.test_project_name), auth=self.test_user_auth)
        self.assertEqual(response.status_code, 200)
        changeDetails = response.json()
        self.assertIsNotNone(changeDetails)
        self.assertEqual(changeDetails.get('project'), self.test_project_name)
        self.assertEqual(changeDetails.get('user'), self.test_user_name)
        self.assertTrue(changeDetails.get('timestamp') > timestamp)
        self.assertEqual(changeDetails.get('change'), 'move')
        self.assertEqual(changeDetails.get('pathname'), "/%s+/test%s/2017-10/Experiment_3/baseline_old" % (self.test_project_name, self.token))
        self.assertEqual(changeDetails.get('target'), "/%s+/test%s/2017-11/Experiment_9/baseline_x" % (self.test_project_name, self.token))
        self.assertEqual(changeDetails.get('mode'), 'cli')
        timestamp = changeDetails.get('timestamp')
        time.sleep(1)

        print("Download folder as package")
        cmd = "%s download %s /test%s/2017-10/Experiment_5 %s/2017-10_Experiment_5.zip" % (self.cli_cmd, self.args, self.token, self.tempdir)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("Target downloaded successfully", output)
        if self.run_localized_tests:
            path = Path("%s/2017-10_Experiment_5.zip" % (self.tempdir))
            self.assertTrue(path.is_file(), output)
            self.assertEquals(16868, path.stat().st_size, output)

        print("Attempt to upload folder using invalid local pathname")
        cmd = "%s upload %s /test%s/no/such/folder /no/such/folder" % (self.cli_cmd, self.args, self.token)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: Can't find specified file or directory", output)
        self.assertTrue(failed, output)

        print("Attempt to download folder using local pathname of existing package file")
        cmd = "%s download %s /test%s/2017-10/Experiment_5 %s/2017-10_Experiment_5.zip" % (self.cli_cmd, self.args, self.token, self.tempdir)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: Specified local pathname already exists", output)
        self.assertTrue(failed, output)

        print("Delete folder with dry-run parameter and verify no actual deletion occurred")
        cmd = "%s delete %s -D /test%s/2017-10/Experiment_4" % (self.cli_cmd, self.args, self.token)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("* Target deleted successfully", output)
        if self.run_localized_tests:
            path = Path("%s/test%s/2017-10/Experiment_4" % (self.staging, self.token))
            self.assertTrue(path.is_dir(), output)

        print("Delete folder")
        cmd = "%s delete %s /test%s/2017-10/Experiment_4" % (self.cli_cmd, self.args, self.token)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("Target deleted successfully", output)
        if self.run_localized_tests:
            path = Path("%s/test%s/2017-10/Experiment_4" % (self.staging, self.token))
            self.assertFalse(path.exists(), output)

        print("Query IDA for last delete data change details and verify change matches last action")
        response = requests.get("%s/dataChanges/%s/last?change=delete" % (self.config["IDA_API_ROOT_URL"], self.test_project_name), auth=self.test_user_auth)
        self.assertEqual(response.status_code, 200)
        changeDetails = response.json()
        self.assertIsNotNone(changeDetails)
        self.assertEqual(changeDetails.get('project'), self.test_project_name)
        self.assertEqual(changeDetails.get('user'), self.test_user_name)
        self.assertTrue(changeDetails.get('timestamp') > timestamp)
        self.assertEqual(changeDetails.get('change'), 'delete')
        self.assertEqual(changeDetails.get('pathname'), "/%s+/test%s/2017-10/Experiment_4" % (self.test_project_name, self.token))
        self.assertIsNone(changeDetails.get('target'))
        self.assertEqual(changeDetails.get('mode'), 'cli')
        timestamp = changeDetails.get('timestamp')
        time.sleep(1)

        print("--- Info Operations")

        print("Upload new folder")
        cmd = "%s upload %s /test%s/2017-12/Experiment_1/baseline %s/2017-08/Experiment_1/baseline" % (self.cli_cmd, self.args, self.token, self.testdata)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("Target uploaded successfully", output)
        if self.run_localized_tests:
            path = Path("%s/test%s/2017-12/Experiment_1/baseline" % (self.staging, self.token))
            self.assertTrue(path.is_dir(), output)
            path = Path("%s/test%s/2017-12/Experiment_1/baseline/test01.dat" % (self.staging, self.token))
            self.assertTrue(path.is_file(), output)
            self.assertEquals(446, path.stat().st_size, output)
            path = Path("%s/test%s/2017-12/Experiment_1/baseline/test02.dat" % (self.staging, self.token))
            self.assertTrue(path.is_file(), output)
            self.assertEquals(1531, path.stat().st_size, output)
            path = Path("%s/test%s/2017-12/Experiment_1/baseline/test03.dat" % (self.staging, self.token))
            self.assertTrue(path.is_file(), output)
            self.assertEquals(2263, path.stat().st_size, output)
            path = Path("%s/test%s/2017-12/Experiment_1/baseline/test04.dat" % (self.staging, self.token))
            self.assertTrue(path.is_file(), output)
            self.assertEquals(3329, path.stat().st_size, output)
            path = Path("%s/test%s/2017-12/Experiment_1/baseline/test05.dat" % (self.staging, self.token))
            self.assertTrue(path.is_file(), output)
            self.assertEquals(3728, path.stat().st_size, output)
            path = Path("%s/test%s/2017-12/Experiment_1/baseline/zero_size_file" % (self.staging, self.token))
            self.assertTrue(path.is_file(), output)
            self.assertEquals(0, path.stat().st_size, output)

        print("Retrieve file info from staging area as plain text")
        cmd = "%s info %s /test%s/2017-12/Experiment_1/baseline/test01.dat" % (self.cli_cmd, self.info_args, self.token)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("project:    %s" % (self.test_project_name), output)
        self.assertIn("area:       staging", output)
        self.assertIn("type:       file", output)
        self.assertIn("pathname:   /test%s/2017-12/Experiment_1/baseline/test01.dat" % (self.token), output)
        self.assertIn("size:       446", output)
        self.assertIn("checksum:   sha256:56293a80e0394d252e995f2debccea8223e4b5b2b150bee212729b3b39ac4d46", output)
        self.assertIn("encoding:   application/octet-stream", output)
        self.assertIn("uploaded:   ", output)
        self.assertIn("modified:   ", output)

        print("Retrieve file info from staging area as JSON")
        cmd = "%s info %s -j /test%s/2017-12/Experiment_1/baseline/test01.dat" % (self.cli_cmd, self.info_args, self.token)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("\"project\": \"%s\"" % (self.test_project_name), output)
        self.assertIn("\"area\": \"staging\"", output)
        self.assertIn("\"type\": \"file\"", output)
        self.assertIn("\"pathname\": \"/test%s/2017-12/Experiment_1/baseline/test01.dat\"" % (self.token), output)
        self.assertIn("\"size\": 446", output)
        self.assertIn("\"checksum\": \"sha256:56293a80e0394d252e995f2debccea8223e4b5b2b150bee212729b3b39ac4d46\"", output)
        self.assertIn("\"encoding\": \"application/octet-stream\"", output)
        self.assertIn("\"uploaded\": ", output)
        self.assertIn("\"modified\": ", output)

        print("Verify no verbose or debug output to stdout from info action")
        cmd = "%s info %s /test%s/2017-12/Experiment_1/baseline/test01.dat 2>/dev/null" % (self.cli_cmd, self.info_args, self.token)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertNotIn("Verifying ", output)
        self.assertNotIn("curl ", output)

        print("Retrieve folder info from staging area")
        cmd = "%s info %s /test%s/2017-12/Experiment_1/baseline" % (self.cli_cmd, self.info_args, self.token)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("project:    %s" % (self.test_project_name), output)
        self.assertIn("area:       staging", output)
        self.assertIn("type:       folder", output)
        self.assertIn("pathname:   /test%s/2017-12/Experiment_1/baseline" % (self.token), output)
        self.assertIn("size:       11297", output)
        self.assertIn("contents:", output)
        self.assertIn("  /test%s/2017-12/Experiment_1/baseline/test01.dat" % (self.token), output)
        self.assertIn("  /test%s/2017-12/Experiment_1/baseline/test02.dat" % (self.token), output)
        self.assertIn("  /test%s/2017-12/Experiment_1/baseline/test03.dat" % (self.token), output)
        self.assertIn("  /test%s/2017-12/Experiment_1/baseline/test04.dat" % (self.token), output)
        self.assertIn("  /test%s/2017-12/Experiment_1/baseline/test05.dat" % (self.token), output)
        self.assertIn("  /test%s/2017-12/Experiment_1/baseline/zero_size_file" % (self.token), output)
        self.assertNotIn(":href>", output)

        print("(freeze folder)")
        data = {"project": self.test_project_name, "pathname": "/test%s/2017-12/Experiment_1/baseline" % (self.token)}
        response = requests.post("%s/freeze" % self.ida_api, json=data, auth=self.test_user_auth, verify=False)
        self.assertEqual(response.status_code, 200)
        if self.run_localized_tests:
            path = Path("%s/test%s/2017-12/Experiment_1/baseline" % (self.frozen, self.token))
            self.assertTrue(path.is_dir(), output)
            path = Path("%s/test%s/2017-12/Experiment_1/baseline" % (self.staging, self.token))
            self.assertFalse(path.exists(), output)

        self.waitForPendingActions(self.test_project_name, self.test_user_auth)
        self.checkForFailedActions(self.test_project_name, self.test_user_auth)

        print("Retrieve file info from frozen area")
        cmd = "%s info %s -f /test%s/2017-12/Experiment_1/baseline/test01.dat" % (self.cli_cmd, self.info_args, self.token)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("project:    %s" % (self.test_project_name), output)
        self.assertIn("area:       frozen", output)
        self.assertIn("type:       file", output)
        self.assertIn("pathname:   /test%s/2017-12/Experiment_1/baseline/test01.dat" % (self.token), output)
        self.assertIn("size:       446", output)
        self.assertIn("checksum:   sha256:56293a80e0394d252e995f2debccea8223e4b5b2b150bee212729b3b39ac4d46", output)
        self.assertIn("encoding:   application/octet-stream", output)
        self.assertIn("pid:        ", output)
        self.assertIn("uploaded:   ", output)
        self.assertIn("modified:   ", output)
        self.assertIn("frozen:     ", output)

        print("Retrieve folder info from frozen area")
        cmd = "%s info %s -f /test%s/2017-12/Experiment_1/baseline" % (self.cli_cmd, self.info_args, self.token)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("project:    %s" % (self.test_project_name), output)
        self.assertIn("area:       frozen", output)
        self.assertIn("type:       folder", output)
        self.assertIn("pathname:   /test%s/2017-12/Experiment_1/baseline" % (self.token), output)
        self.assertIn("size:       11297", output)
        self.assertIn("contents:", output)
        self.assertIn("  /test%s/2017-12/Experiment_1/baseline/test01.dat" % (self.token), output)
        self.assertIn("  /test%s/2017-12/Experiment_1/baseline/test02.dat" % (self.token), output)
        self.assertIn("  /test%s/2017-12/Experiment_1/baseline/test03.dat" % (self.token), output)
        self.assertIn("  /test%s/2017-12/Experiment_1/baseline/test04.dat" % (self.token), output)
        self.assertIn("  /test%s/2017-12/Experiment_1/baseline/test05.dat" % (self.token), output)
        self.assertIn("  /test%s/2017-12/Experiment_1/baseline/zero_size_file" % (self.token), output)
        self.assertNotIn(":href>", output)

        print("Attempt to retrieve file info from staging area using invalid target pathname")
        cmd = "%s info %s /test%s/no/such/file.txt" % (self.cli_cmd, self.info_args, self.token)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: Specified target not found", output)
        self.assertTrue(failed, output)

        print("Attempt to retrieve folder info from staging area using invalid target pathname")
        cmd = "%s info %s /test%s/no/such/folder" % (self.cli_cmd, self.info_args, self.token)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: Specified target not found", output)
        self.assertTrue(failed, output)

        print("Attempt to retrieve file info from frozen area using invalid target pathname")
        cmd = "%s info %s -f /test%s/no/such/file.txt" % (self.cli_cmd, self.info_args, self.token)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: Specified target not found", output)
        self.assertTrue(failed, output)

        print("Attempt to retrieve folder info from frozen area using invalid target pathname")
        cmd = "%s info %s -f /test%s/no/such/folder" % (self.cli_cmd, self.info_args, self.token)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: Specified target not found", output)
        self.assertTrue(failed, output)

        if self.run_trusted_tests:

            print("--- Locking and Scope Collisions")

            # NOTE: It is sufficient to simply use service locking for testing all CLI behavior
            # related to lock and scope collision, without having to simulate any initiating
            # actions and test actual pathname collisions. This is because the behavioral tests
            # for the scope collision functionality already cover actual collision use cases,
            # and all that must be checked here is that the CLI script queries the scopeOK API
            # endpoint before each relevant operation and exits with an error if a 409 response
            # is received. It doesn't matter whether the 409 response is due to the service being
            # locked or an actual pathname collision.

            print("Lock service")
            response = requests.post("%s/lock/all" % (self.ida_api), auth=self.admin_user_auth, verify=False)
            self.assertEqual(response.status_code, 200)

            print("Verify that service is locked")
            response = requests.get("%s/lock/all" % (self.ida_api), auth=self.test_user_auth, verify=False)
            self.assertEqual(response.status_code, 200)

            print("Attempt to upload file while service is locked")
            cmd = "%s upload %s /test%s/2017-08/Experiment_1/test01.dat %s/2017-08/Experiment_1/test01.dat" % (self.cli_cmd, self.args, self.token, self.testdata)
            failed = False
            try:
                output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
            except subprocess.CalledProcessError as error:
                failed = True
                output = error.output.decode(sys.stdout.encoding)
                self.assertIn("Error: Specified target conflicts with an ongoing action", output)
            self.assertTrue(failed, output)
    
            print("Attempt to rename file while service is locked")
            cmd = "%s move %s /test%s/2017-08/Experiment_1/test01b.dat /test%s/2017-08/Experiment_1/test01.dat" % (self.cli_cmd, self.args, self.token, self.token)
            failed = False
            try:
                output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
            except subprocess.CalledProcessError as error:
                failed = True
                output = error.output.decode(sys.stdout.encoding)
                self.assertIn("Error: Specified target conflicts with an ongoing action", output)
            self.assertTrue(failed, output)
    
            print("Attempt to delete file while service is locked")
            cmd = "%s delete %s /test%s/2017-08/Experiment_1/test01.dat" % (self.cli_cmd, self.args, self.token)
            failed = False
            try:
                output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
            except subprocess.CalledProcessError as error:
                failed = True
                output = error.output.decode(sys.stdout.encoding)
                self.assertIn("Error: Specified target conflicts with an ongoing action", output)
            self.assertTrue(failed, output)
    
            print("Attempt to upload folder while service is locked")
            cmd = "%s upload %s /test%s/2017-08/Experiment_1/baseline6 %s/2017-08/Experiment_2/baseline" % (self.cli_cmd, self.args, self.token, self.testdata)
            failed = False
            try:
                output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
            except subprocess.CalledProcessError as error:
                failed = True
                output = error.output.decode(sys.stdout.encoding)
                self.assertIn("Error: Specified target conflicts with an ongoing action", output)
            self.assertTrue(failed, output)
    
            print("Attempt to rename folder while service is locked")
            cmd = "%s move %s /test%s/2017-08/Experiment_1 /test%s/2017-08/Experiment_9" % (self.cli_cmd, self.args, self.token, self.token)
            failed = False
            try:
                output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
            except subprocess.CalledProcessError as error:
                failed = True
                output = error.output.decode(sys.stdout.encoding)
                self.assertIn("Error: Specified target conflicts with an ongoing action", output)
            self.assertTrue(failed, output)
    
            print("Attempt to delete folder while service is locked")
            cmd = "%s delete %s /test%s/2017-08/Experiment_1" % (self.cli_cmd, self.args, self.token)
            failed = False
            try:
                output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
            except subprocess.CalledProcessError as error:
                failed = True
                output = error.output.decode(sys.stdout.encoding)
                self.assertIn("Error: Specified target conflicts with an ongoing action", output)
            self.assertTrue(failed, output)
    
            print("Unlock service")
            response = requests.delete("%s/lock/all" % (self.ida_api), auth=self.admin_user_auth, verify=False)
            self.assertEqual(response.status_code, 200)
    
            print("Verify that service is unlocked")
            response = requests.get("%s/lock/all" % (self.ida_api), auth=self.admin_user_auth, verify=False)
            self.assertEqual(response.status_code, 404)
        
        print("(delete test data folder from staging area)")
        cmd = "%s delete %s /test%s" % (self.cli_cmd, self.args, self.token)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("Target deleted successfully", output)
        if self.run_localized_tests:
            path = Path("%s/test%s" % (self.staging, self.token))
            self.assertFalse(path.is_dir(), output)

        print("(delete test data folder from frozen area)")
        data = {"project": self.test_project_name, "pathname": "/test%s" % (self.token)}
        response = requests.post("%s/delete" % self.ida_api, json=data, auth=self.test_user_auth, verify=False)
        self.assertEqual(response.status_code, 200)
        if self.run_localized_tests:
            path = Path("%s/test%s" % (self.frozen, self.token))
            self.assertFalse(path.exists(), output)
    
        self.waitForPendingActions(self.test_project_name, self.test_user_auth)
        self.checkForFailedActions(self.test_project_name, self.test_user_auth)

        self.success = True
