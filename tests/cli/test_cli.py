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
import urllib
import unittest
import subprocess
import os
import sys
import socket
import shutil

from pathlib import Path
from tests.common.utils import load_configuration


class TestIdaCli(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        print("=== tests/cli/test_cli")

    def setUp(self):

        self.config = load_configuration()

        self.hostname = socket.gethostname()

        self.cli = "%s/ida" % self.config["IDA_CLI_ROOT"]
        self.tempdir = "%s/tests/cli/tmp" % (self.config["IDA_CLI_ROOT"])
        self.ignore_file = "-i %s/tests/cli/ida-ignore" % (self.config["IDA_CLI_ROOT"])
        self.config_file = "%s/ida-config" % self.tempdir
        self.args = "-x -c %s" % self.config_file

        self.api = self.config["IDA_API_ROOT_URL"]
        self.project_name = "test_project_cli"
        self.user_name = "test_user_cli"
        self.pso_user_name = "%s%s" % (self.config["PROJECT_USER_PREFIX"], self.project_name)
        self.ida_project = "sudo -u %s %s/admin/ida_project" % (self.config["HTTPD_USER"], self.config["ROOT"])
        self.ida_user = "sudo -u %s %s/admin/ida_user" % (self.config["HTTPD_USER"], self.config["ROOT"])
        self.admin_user = (self.config["NC_ADMIN_USER"], self.config["NC_ADMIN_PASS"])
        self.pso_user = (self.pso_user_name, self.config["PROJECT_USER_PASS"])
        self.test_user = (self.user_name, self.config["TEST_USER_PASS"])
        self.storage_root = self.config["STORAGE_OC_DATA_ROOT"]
        self.staging = "%s/%s/files/%s+" % (self.storage_root, self.pso_user_name, self.project_name)
        self.frozen = "%s/%s/files/%s" % (self.storage_root, self.pso_user_name, self.project_name)
        self.testdata = "%s/tests/testdata" % (self.config["ROOT"])

        # Ensure CLI script exists where specified
        path = Path(self.cli)
        self.assertTrue(path.is_file())

        # Prefix IDA CLI script pathname with test user password from configuration
        self.cli = "IDA_PASSWORD=\"%s\" %s" % (self.config["TEST_USER_PASS"], self.cli)

        # Ensure test data root exists where specified and is directory
        path = Path(self.testdata)
        self.assertTrue(path.is_dir())

        # Clear any residual accounts, if they exist from a prior run
        self.success = True
        self.config["NO_FLUSH_AFTER_TESTS"] = "false"
        self.tearDown()
        self.success = False
        self.config["NO_FLUSH_AFTER_TESTS"] = "true"

        print("(initializing)")

        # Ensure temp dir exists and is empty
        path = Path(self.tempdir)
        if path.exists():
            shutil.rmtree(self.tempdir, ignore_errors=True)
        path.mkdir()

        # Build test ida-config files based on /var/ida/config/config.sh definitions
        f = open("%s/ida-config" % self.tempdir, "w")
        f.write("IDA_HOST=\"https://%s\"\n" % self.hostname)
        f.write("IDA_PROJECT=\"test_project_cli\"\n")
        f.write("IDA_USERNAME=\"test_user_cli\"\n")
        f.write("IDA_PASSWORD=\"%s\"\n" % self.config["TEST_USER_PASS"])
        f.close()
        f = open("%s/ida-config-invalid-username" % self.tempdir, "w")
        f.write("IDA_HOST=\"https://%s\"\n" % self.hostname)
        f.write("IDA_PROJECT=\"test_project_cli\"\n")
        f.write("IDA_USERNAME=\"invalid\"\n")
        f.write("IDA_PASSWORD=\"%s\"\n" % self.config["TEST_USER_PASS"])
        f.close()
        f = open("%s/ida-config-invalid-password" % self.tempdir, "w")
        f.write("IDA_HOST=\"https://%s\"\n" % self.hostname)
        f.write("IDA_PROJECT=\"test_project_cli\"\n")
        f.write("IDA_USERNAME=\"test_user_cli\"\n")
        f.write("IDA_PASSWORD=\"invalid\"\n")
        f.close()

        # Clear any curl cookies

        cmd = "%s/tests/utils/clear-cookies" % self.config["IDA_CLI_ROOT"]
        result = os.system(cmd)
        self.assertEquals(result, 0)

        # Initialize test accounts

        cmd = "sudo -u %s %s/tests/utils/initialize-test-accounts" % (self.config["HTTPD_USER"], self.config["IDA_CLI_ROOT"])
        result = os.system(cmd)
        self.assertEquals(result, 0)


    def tearDown(self):

        # Always unlock the service, even if a test failed

        print("Unlock service")
        response = requests.delete("%s/lock/all" % (self.api), auth=self.admin_user, verify=False)
        self.assertEqual(response.status_code, 200, "Failed to unlock service while cleaning up!")

        print("Verify that service is unlocked")
        response = requests.get("%s/lock/all" % (self.api), auth=self.admin_user, verify=False)
        self.assertEqual(response.status_code, 404, "Failed to unlock service while cleaning up!")

        # Flush all test projects, user accounts, and data, but only if all tests passed,
        # else leave projects and data as-is so test project state can be inspected

        if self.success and self.config.get("NO_FLUSH_AFTER_TESTS", "false") == "false":

            print("(cleaning)")

            shutil.rmtree(self.tempdir, ignore_errors=True)

            cmd = "sudo -u %s %s/tests/utils/initialize-test-accounts flush" % (self.config["HTTPD_USER"], self.config["IDA_CLI_ROOT"])
            result = os.system(cmd)
            self.assertEquals(result, 0)

        self.assertTrue(self.success)


    def test_ida_cli(self):

        print("--- Parameters and Credentials")

        print("Check usage guide output when no parameters provided")
        try:
            output = subprocess.check_output(self.cli, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("Usage:", output)
        self.assertIn("checksum:", output)

        print("Attempt to use project name with invalid characters")
        cmd = "%s info %s -p bad@project:name+ /" % (self.cli, self.args)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: Invalid characters in project name.", output)
        self.assertTrue(failed, output)

        print("Attempt to use invalid action")
        cmd = "%s unknown %s /Contact.txt %s/Contact.txt" % (self.cli, self.args, self.testdata)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: Invalid action.", output)
        self.assertTrue(failed, output)


        print("Attempt to upload file to non-existent service")
        cmd = "%s upload %s -t \"http://no.such.service\" /Contact.txt %s/Contact.txt" % (self.cli, self.args, self.testdata)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: Authentication failed.", output)
        self.assertTrue(failed, output)

        print("Attempt to upload file to non-existent project")
        cmd = "%s upload %s -p no_such_project /Contact.txt %s/Contact.txt" % (self.cli, self.args, self.testdata)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: Authentication failed.", output)
        self.assertTrue(failed, output)

        print("Attempt to upload file using invalid username")
        cmd = "%s upload %s-invalid-username /Contact.txt %s/Contact.txt" % (self.cli, self.args, self.testdata)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: Authentication failed.", output)
        self.assertTrue(failed, output)

        print("Attempt to upload file using invalid password")
        cmd = "%s upload %s-invalid-password /Contact.txt %s/Contact.txt" % (self.cli, self.args, self.testdata)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: Authentication failed.", output)
        self.assertTrue(failed, output)

        print("Attempt to upload file using unspecified target pathname")
        cmd = "%s upload %s %s/Contact.txt" % (self.cli, self.args, self.testdata)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: Missing target pathname.", output)
        self.assertTrue(failed, output)

        print("Attempt to upload file to pathname exceeding maximum allowed URL encoded pathname length")
        cmd = "%s upload %s /XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX_201_characters %s/Contact.txt" % (self.cli, self.args, self.testdata)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: URL encoded pathname exceeds maximum allowed length of 200 characters:", output)
        self.assertTrue(failed, output)

        print("Attempt to upload file using unspecified local pathname")
        cmd = "%s upload %s /Contact.txt" % (self.cli, self.args)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: Missing local pathname.", output)
        self.assertTrue(failed, output)

        print("Attempt to upload folder using staging root as target pathname")
        cmd = "%s upload %s / %s/2017-08" % (self.cli, self.args, self.testdata)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: Target pathname invalid or missing.", output)
        self.assertTrue(failed, output)

        print("Attempt to upload folder using file system root as local pathname")
        cmd = "%s upload %s /Data /" % (self.cli, self.args)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: Local pathname invalid or missing.", output)
        self.assertTrue(failed, output)

        print("Attempt to upload file with missing configuration file pathname")
        cmd = "%s upload -x -c" % (self.cli)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: Missing configuration file pathname.", output)
        self.assertTrue(failed, output)

        print("Attempt to upload file using non-existent configuration file")
        cmd = "%s upload -x -c /no/such/config/file /Contact.txt %s/Contact.txt" % (self.cli, self.testdata)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: Can't find specified configuration file.", output)
        self.assertTrue(failed, output)

        print("Attempt to upload file with missing ignore file pathname")
        cmd = "%s upload %s -i" % (self.cli, self.args)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: Missing ignore file pathname.", output)
        self.assertTrue(failed, output)

        print("Attempt to upload file using non-existent ignore file")
        cmd = "%s upload %s -i /no/such/ignore/file /Contact.txt %s/Contact.txt" % (self.cli, self.args, self.testdata)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: Can't find specified ignore file.", output)
        self.assertTrue(failed, output)

        print("Attempt to upload multiple files to target folder by specifying multiple local pathnames")
        cmd = "%s upload %s /Legal %s/Contact.txt %s/License.txt" % (self.cli, self.args, self.testdata, self.testdata)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: Too many parameters specified.", output)
        self.assertTrue(failed, output)

        print("Attempt to delete multiple files by specifying multiple target pathnames")
        cmd = "%s delete %s /Contact.txt /License.txt" % (self.cli, self.args)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: Too many parameters specified.", output)
        self.assertTrue(failed, output)

        print("--- File Operations")

        print("Upload new file")
        cmd = "%s upload %s /Contact.txt %s/Contact.txt" % (self.cli, self.args, self.testdata)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("Target uploaded successfully.", output)
        path = Path("%s/Contact.txt" % (self.staging))
        self.assertTrue(path.is_file(), output)

        print("Update existing file")
        cmd = "%s upload %s /Contact.txt %s/Contact.txt" % (self.cli, self.args, self.testdata)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("Target uploaded successfully.", output)
        path = Path("%s/Contact.txt" % (self.staging))
        self.assertTrue(path.is_file(), output)

        print("Upload file without initial slash in target pathname")
        cmd = "%s upload %s License.txt %s/License.txt" % (self.cli, self.args, self.testdata)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("Target uploaded successfully.", output)
        path = Path("%s/License.txt" % (self.staging))
        self.assertTrue(path.is_file(), output)

        print("Upload file with relative local pathname")
        cmd = "cd %s/2017-08; %s upload %s /License2.txt ../License.txt" % (self.testdata, self.cli, self.args)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("Target uploaded successfully.", output)
        path = Path("%s/License2.txt" % (self.staging))
        self.assertTrue(path.is_file(), output)

        print("Upload zero size file")
        cmd = "%s upload %s /zero_size_file %s/2017-08/Experiment_1/zero_size_file" % (self.cli, self.args, self.testdata)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("Target uploaded successfully.", output)
        path = Path("%s/zero_size_file" % (self.staging))
        self.assertTrue(path.is_file(), output)
        self.assertEquals(0, path.stat().st_size, output)

        print("Copy file within staging")
        cmd = "%s copy %s /Contact.txt /a/b/c/Contact.txt" % (self.cli, self.args)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("Target copied successfully.", output)
        path = Path("%s/Contact.txt" % (self.staging))
        self.assertTrue(path.is_file(), output)
        path = Path("%s/a/b/c/Contact.txt" % (self.staging))
        self.assertTrue(path.is_file(), output)

        print("(freeze file)")
        data = {"project": self.project_name, "pathname": "/a/b/c/Contact.txt"}
        response = requests.post("%s/freeze" % self.api, json=data, auth=self.test_user, verify=False)
        self.assertEqual(response.status_code, 200)
        path = Path("%s/a/b/c/Contact.txt" % (self.frozen))
        self.assertTrue(path.is_file(), output)
        path = Path("%s/a/b/c/Contact.txt" % (self.staging))
        self.assertFalse(path.exists(), output)

        print("Copy file from frozen area to staging area")
        cmd = "%s copy %s -f /a/b/c/Contact.txt /a/b/c/Contact.txt" % (self.cli, self.args)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("Target copied successfully.", output)
        path = Path("%s/a/b/c/Contact.txt" % (self.frozen))
        self.assertTrue(path.is_file(), output)
        path = Path("%s/a/b/c/Contact.txt" % (self.staging))
        self.assertTrue(path.is_file(), output)

        print("Copy zero size file")
        cmd = "%s copy %s /zero_size_file /a/b/c/zero_size_file" % (self.cli, self.args)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("Target copied successfully.", output)
        path = Path("%s/zero_size_file" % (self.staging))
        self.assertTrue(path.is_file(), output)
        self.assertEquals(0, path.stat().st_size, output)
        path = Path("%s/a/b/c/zero_size_file" % (self.staging))
        self.assertTrue(path.is_file(), output)
        self.assertEquals(0, path.stat().st_size, output)

        print("Rename file")
        cmd = "%s move %s /Contact.txt /Contact2.txt" % (self.cli, self.args)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("Target moved successfully.", output)
        path = Path("%s/Contact.txt" % (self.staging))
        self.assertFalse(path.exists(), output)
        path = Path("%s/Contact2.txt" % (self.staging))
        self.assertTrue(path.is_file(), output)

        print("Move file")
        cmd = "%s move %s /Contact2.txt /x/y/z/Contact.txt" % (self.cli, self.args)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("Target moved successfully.", output)
        path = Path("%s/Contact2.txt" % (self.staging))
        self.assertFalse(path.exists(), output)
        path = Path("%s/x/y/z/Contact.txt" % (self.staging))
        self.assertTrue(path.is_file(), output)

        print("Download file")
        cmd = "%s download %s /x/y/z/Contact.txt %s/a/b/c/Contact.txt" % (self.cli, self.args, self.tempdir)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("Target downloaded successfully.", output)
        path = Path("%s/a/b/c/Contact.txt" % (self.tempdir))
        self.assertTrue(path.is_file(), output)
        self.assertEquals(2263, path.stat().st_size, output)

        print("Attempt to upload file using invalid local pathname")
        cmd = "%s upload %s /no/such/file.txt /no/such/file.txt" % (self.cli, self.args)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: Can't find specified file or directory.", output)
        self.assertTrue(failed, output)

        print("Attempt to copy file to existing target pathname")
        cmd = "%s copy %s /License2.txt /x/y/z/Contact.txt" % (self.cli, self.args)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: Specified new target already exists.", output)
        self.assertTrue(failed, output)

        print("Attempt to move file to existing target pathname")
        cmd = "%s move %s /License2.txt /x/y/z/Contact.txt" % (self.cli, self.args)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: Specified new target already exists.", output)
        self.assertTrue(failed, output)

        print("Attempt to upload file to frozen area")
        cmd = "%s upload %s -f /LicenseX.txt %s/License.txt" % (self.cli, self.args, self.testdata)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: The -f option is not allowed for the specified action.", output)
        self.assertTrue(failed, output)

        print("Attempt to move frozen file")
        cmd = "%s move %s -f /License.txt /LicenseX.txt" % (self.cli, self.args)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: The -f option is not allowed for the specified action.", output)
        self.assertTrue(failed, output)

        print("Attempt to delete frozen file")
        cmd = "%s delete %s -f /License.txt" % (self.cli, self.args)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: The -f option is not allowed for the specified action.", output)
        self.assertTrue(failed, output)

        print("Attempt to download file using invalid target pathname")
        cmd = "%s download %s /no/such/file.txt %s/no/such/file.txt" % (self.cli, self.args, self.tempdir)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: Specified target not found.", output)
        self.assertTrue(failed, output)

        print("Attempt to download file using local pathname of existing file")
        cmd = "%s download %s /x/y/z/Contact.txt %s/a/b/c/Contact.txt" % (self.cli, self.args, self.tempdir)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: Specified local pathname already exists.", output)
        self.assertTrue(failed, output)

        print("Delete file")
        cmd = "%s delete %s /x/y/z/Contact.txt" % (self.cli, self.args)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("Target deleted successfully.", output)
        path = Path("%s/x/y/z/Contact.txt" % (self.staging))
        self.assertFalse(path.exists(), output)

        print("--- Folder Operations")

        print("Upload new folder")
        cmd = "%s upload %s /2017-08/Experiment_1 %s/2017-08/Experiment_1" % (self.cli, self.args, self.testdata)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("Target uploaded successfully.", output)
        path = Path("%s/2017-08/Experiment_1/baseline" % (self.staging))
        self.assertTrue(path.is_dir(), output)
        path = Path("%s/2017-08/Experiment_1/baseline/test01.dat" % (self.staging))
        self.assertTrue(path.is_file(), output)
        self.assertEquals(446, path.stat().st_size, output)
        path = Path("%s/2017-08/Experiment_1/baseline/test02.dat" % (self.staging))
        self.assertTrue(path.is_file(), output)
        self.assertEquals(1531, path.stat().st_size, output)
        path = Path("%s/2017-08/Experiment_1/baseline/test03.dat" % (self.staging))
        self.assertTrue(path.is_file(), output)
        self.assertEquals(2263, path.stat().st_size, output)
        path = Path("%s/2017-08/Experiment_1/baseline/test04.dat" % (self.staging))
        self.assertTrue(path.is_file(), output)
        self.assertEquals(3329, path.stat().st_size, output)
        path = Path("%s/2017-08/Experiment_1/baseline/test05.dat" % (self.staging))
        self.assertTrue(path.is_file(), output)
        self.assertEquals(3728, path.stat().st_size, output)

        print("Upload additional files to existing folder")
        cmd = "%s upload %s /2017-08/Experiment_1/baseline2 %s/2017-08/Experiment_2/baseline" % (self.cli, self.args, self.testdata)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("Target uploaded successfully.", output)
        path = Path("%s/2017-08/Experiment_1/baseline2" % (self.staging))
        self.assertTrue(path.is_dir(), output)
        path = Path("%s/2017-08/Experiment_1/baseline2/test01.dat" % (self.staging))
        self.assertTrue(path.is_file(), output)
        self.assertEquals(446, path.stat().st_size, output)

        print("Upload folder without initial slash in target pathname")
        cmd = "%s upload %s 2017-08/Experiment_1/baseline3 %s/2017-08/Experiment_2/baseline" % (self.cli, self.args, self.testdata)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("Target uploaded successfully.", output)
        path = Path("%s/2017-08/Experiment_1/baseline3" % (self.staging))
        self.assertTrue(path.is_dir(), output)
        path = Path("%s/2017-08/Experiment_1/baseline3/test01.dat" % (self.staging))
        self.assertTrue(path.is_file(), output)
        self.assertEquals(446, path.stat().st_size, output)

        print("Upload folder with trailing slash in target pathname")
        cmd = "%s upload %s /2017-08/Experiment_1/baseline4/ %s/2017-08/Experiment_2/baseline" % (self.cli, self.args, self.testdata)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("Target uploaded successfully.", output)
        path = Path("%s/2017-08/Experiment_1/baseline4" % (self.staging))
        self.assertTrue(path.is_dir(), output)
        path = Path("%s/2017-08/Experiment_1/baseline4/test01.dat" % (self.staging))
        self.assertTrue(path.is_file(), output)
        self.assertEquals(446, path.stat().st_size, output)

        print("Upload folder with trailing slash in local pathname")
        cmd = "%s upload %s /2017-08/Experiment_1/baseline5 %s/2017-08/Experiment_2/baseline/" % (self.cli, self.args, self.testdata)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("Target uploaded successfully.", output)
        path = Path("%s/2017-08/Experiment_1/baseline5" % (self.staging))
        self.assertTrue(path.is_dir(), output)
        path = Path("%s/2017-08/Experiment_1/baseline5/test01.dat" % (self.staging))
        self.assertTrue(path.is_file(), output)
        self.assertEquals(446, path.stat().st_size, output)

        print("Upload folder with relative local pathname")
        cmd = "cd %s/2017-08/Experiment_2; %s upload %s /2017-08/Experiment_1/baseline6 ./baseline" % (self.testdata, self.cli, self.args)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("Target uploaded successfully.", output)
        path = Path("%s/2017-08/Experiment_1/baseline6" % (self.staging))
        self.assertTrue(path.is_dir(), output)
        path = Path("%s/2017-08/Experiment_1/baseline6/test01.dat" % (self.staging))
        self.assertTrue(path.is_file(), output)
        self.assertEquals(446, path.stat().st_size, output)

        print("Upload folder with ignore patterns")
        cmd = "%s upload %s %s /2017-10 %s/2017-10" % (self.cli, self.args, self.ignore_file, self.testdata)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("Target uploaded successfully.", output)
        path = Path("%s/2017-10/Experiment_3/baseline" % (self.staging))
        self.assertTrue(path.is_dir(), output)
        path = Path("%s/2017-10/Experiment_3/baseline/test01.dat" % (self.staging))
        self.assertTrue(path.is_file(), output)
        self.assertEquals(446, path.stat().st_size, output)
        path = Path("%s/2017-10/.DS_Store" % (self.staging))
        self.assertFalse(path.exists(), output)
        path = Path("%s/2017-10/Experiment_3/test05.dat" % (self.staging))
        self.assertFalse(path.exists(), output)
        path = Path("%s/2017-10/Experiment_3/baseline/test05.dat" % (self.staging))
        self.assertFalse(path.exists(), output)
        path = Path("%s/2017-10/.hidden_folder" % (self.staging))
        self.assertTrue(path.exists(), output)
        path = Path("%s/2017-10/.hidden_folder/test.dat" % (self.staging))
        self.assertTrue(path.exists(), output)
        path = Path("%s/2017-10/Experiment_3/.hidden_file" % (self.staging))
        self.assertFalse(path.exists(), output)

        print("Upload folder with files containing special characters")
        cmd = "%s upload %s /Special\ Characters %s/Special\ Characters" % (self.cli, self.args, self.testdata)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("Target uploaded successfully.", output)
        path = Path("%s/Special Characters" % (self.staging))
        self.assertTrue(path.is_dir(), output)
        path = Path("%s/Special Characters/file_with_ä_and_ö_and_even_å_oh_my.dat" % (self.staging))
        self.assertTrue(path.is_file(), output)
        self.assertEquals(446, path.stat().st_size, output)
        path = Path("%s/Special Characters/file with spaces and [brackets] {etc}" % (self.staging))
        self.assertTrue(path.is_file(), output)
        self.assertEquals(446, path.stat().st_size, output)
        path = Path("%s/Special Characters/$file with spaces and special characters #@äÖ+\'^.dat&" % (self.staging))
        self.assertTrue(path.is_file(), output)
        self.assertEquals(446, path.stat().st_size, output)

        print("Copy folder within staging area")
        cmd = "%s copy %s /2017-10/Experiment_3/baseline /2017-11/Experiment_8/baseline" % (self.cli, self.args)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("Target copied successfully.", output)
        path = Path("%s/2017-10/Experiment_3/baseline" % (self.staging))
        self.assertTrue(path.is_dir(), output)
        path = Path("%s/2017-10/Experiment_3/baseline/zero_size_file" % (self.staging))
        self.assertTrue(path.is_file(), output)
        self.assertEquals(0, path.stat().st_size, output)
        path = Path("%s/2017-11/Experiment_8/baseline" % (self.staging))
        self.assertTrue(path.is_dir(), output)
        path = Path("%s/2017-11/Experiment_8/baseline/zero_size_file" % (self.staging))
        self.assertTrue(path.is_file(), output)
        self.assertEquals(0, path.stat().st_size, output)

        print("(freeze folder)")
        data = {"project": self.project_name, "pathname": "/2017-11/Experiment_8"}
        response = requests.post("%s/freeze" % self.api, json=data, auth=self.test_user, verify=False)
        self.assertEqual(response.status_code, 200)
        path = Path("%s/2017-11/Experiment_8" % (self.frozen))
        self.assertTrue(path.is_dir(), output)
        path = Path("%s/2017-11/Experiment_8" % (self.staging))
        self.assertFalse(path.exists(), output)

        print("Copy folder from frozen area to staging area")
        cmd = "%s copy %s -f /2017-11/Experiment_8/baseline /2017-11/Experiment_8/baseline" % (self.cli, self.args)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("Target copied successfully.", output)
        path = Path("%s/2017-11/Experiment_8/baseline" % (self.frozen))
        self.assertTrue(path.is_dir(), output)
        path = Path("%s/2017-11/Experiment_8/baseline/zero_size_file" % (self.frozen))
        self.assertTrue(path.is_file(), output)
        self.assertEquals(0, path.stat().st_size, output)
        path = Path("%s/2017-11/Experiment_8/baseline" % (self.staging))
        self.assertTrue(path.is_dir(), output)
        path = Path("%s/2017-11/Experiment_8/baseline/zero_size_file" % (self.staging))
        self.assertTrue(path.is_file(), output)
        self.assertEquals(0, path.stat().st_size, output)

        print("Rename folder")
        cmd = "%s move %s /2017-10/Experiment_3/baseline /2017-10/Experiment_3/baseline_old" % (self.cli, self.args)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("Target moved successfully.", output)
        path = Path("%s/2017-10/Experiment_3/baseline" % (self.staging))
        self.assertFalse(path.exists(), output)
        path = Path("%s/2017-10/Experiment_3/baseline_old" % (self.staging))
        self.assertTrue(path.is_dir(), output)

        print("Move folder")
        cmd = "%s move %s /2017-10/Experiment_3/baseline_old /2017-11/Experiment_9/baseline_x" % (self.cli, self.args)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("Target moved successfully.", output)
        path = Path("%s/2017-10/Experiment_3/baseline_old" % (self.staging))
        self.assertFalse(path.exists(), output)
        path = Path("%s/2017-11/Experiment_9/baseline_x" % (self.staging))
        self.assertTrue(path.is_dir(), output)
        path = Path("%s/2017-11/Experiment_9/baseline_x/zero_size_file" % (self.staging))
        self.assertTrue(path.is_file(), output)
        self.assertEquals(0, path.stat().st_size, output)

        print("Download folder as package")
        cmd = "%s download %s /2017-10/Experiment_5 %s/2017-10_Experiment_5.zip" % (self.cli, self.args, self.tempdir)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("Target downloaded successfully.", output)
        path = Path("%s/2017-10_Experiment_5.zip" % (self.tempdir))
        self.assertTrue(path.is_file(), output)
        self.assertEquals(16868, path.stat().st_size, output)

        print("Attempt to upload folder using invalid local pathname")
        cmd = "%s upload %s /no/such/folder /no/such/folder" % (self.cli, self.args)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: Can't find specified file or directory.", output)
        self.assertTrue(failed, output)

        print("Attempt to download folder using local pathname of existing package file")
        cmd = "%s download %s /2017-10/Experiment_5 %s/2017-10_Experiment_5.zip" % (self.cli, self.args, self.tempdir)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: Specified local pathname already exists.", output)
        self.assertTrue(failed, output)

        print("Delete folder")
        cmd = "%s delete %s /2017-10/Experiment_4" % (self.cli, self.args)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("Target deleted successfully.", output)
        path = Path("%s/2017-10/Experiment_4" % (self.staging))
        self.assertFalse(path.is_dir(), output)

        print("--- Info Operations")

        print("Upload new folder")
        cmd = "%s upload %s /2017-12/Experiment_1/baseline %s/2017-08/Experiment_1/baseline" % (self.cli, self.args, self.testdata)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("Target uploaded successfully.", output)
        path = Path("%s/2017-12/Experiment_1/baseline" % (self.staging))
        self.assertTrue(path.is_dir(), output)
        path = Path("%s/2017-12/Experiment_1/baseline/test01.dat" % (self.staging))
        self.assertTrue(path.is_file(), output)
        self.assertEquals(446, path.stat().st_size, output)
        path = Path("%s/2017-12/Experiment_1/baseline/test02.dat" % (self.staging))
        self.assertTrue(path.is_file(), output)
        self.assertEquals(1531, path.stat().st_size, output)
        path = Path("%s/2017-12/Experiment_1/baseline/test03.dat" % (self.staging))
        self.assertTrue(path.is_file(), output)
        self.assertEquals(2263, path.stat().st_size, output)
        path = Path("%s/2017-12/Experiment_1/baseline/test04.dat" % (self.staging))
        self.assertTrue(path.is_file(), output)
        self.assertEquals(3329, path.stat().st_size, output)
        path = Path("%s/2017-12/Experiment_1/baseline/test05.dat" % (self.staging))
        self.assertTrue(path.is_file(), output)
        self.assertEquals(3728, path.stat().st_size, output)
        path = Path("%s/2017-12/Experiment_1/baseline/zero_size_file" % (self.staging))
        self.assertTrue(path.is_file(), output)
        self.assertEquals(0, path.stat().st_size, output)

        print("Retrieve file info from staging area")
        cmd = "%s info %s /2017-12/Experiment_1/baseline/test01.dat" % (self.cli, self.args)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("project:    %s" % self.project_name, output)
        self.assertIn("area:       staging", output)
        self.assertIn("type:       file", output)
        self.assertIn("pathname:   /2017-12/Experiment_1/baseline/test01.dat", output)
        self.assertIn("size:       446", output)
        self.assertIn("encoding:   application/octet-stream", output)
        self.assertIn("modified:   ", output)

        print("Retrieve folder info from staging area")
        cmd = "%s info %s /2017-12/Experiment_1/baseline" % (self.cli, self.args)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("project:    %s" % self.project_name, output)
        self.assertIn("area:       staging", output)
        self.assertIn("type:       folder", output)
        self.assertIn("pathname:   /2017-12/Experiment_1/baseline", output)
        self.assertIn("size:       11297", output)
        self.assertIn("contents:", output)
        self.assertIn("  /2017-12/Experiment_1/baseline/test01.dat", output)
        self.assertIn("  /2017-12/Experiment_1/baseline/test02.dat", output)
        self.assertIn("  /2017-12/Experiment_1/baseline/test03.dat", output)
        self.assertIn("  /2017-12/Experiment_1/baseline/test04.dat", output)
        self.assertIn("  /2017-12/Experiment_1/baseline/test05.dat", output)
        self.assertIn("  /2017-12/Experiment_1/baseline/zero_size_file", output)
        self.assertNotIn(":href>", output)

        print("(freeze folder)")
        data = {"project": self.project_name, "pathname": "/2017-12/Experiment_1/baseline"}
        response = requests.post("%s/freeze" % self.api, json=data, auth=self.test_user, verify=False)
        self.assertEqual(response.status_code, 200)
        path = Path("%s/2017-12/Experiment_1/baseline" % (self.frozen))
        self.assertTrue(path.is_dir(), output)
        path = Path("%s/2017-12/Experiment_1/baseline" % (self.staging))
        self.assertFalse(path.exists(), output)

        print("Retrieve file info from frozen area")
        cmd = "%s info %s -f /2017-12/Experiment_1/baseline/test01.dat" % (self.cli, self.args)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("project:    %s" % self.project_name, output)
        self.assertIn("area:       frozen", output)
        self.assertIn("type:       file", output)
        self.assertIn("pathname:   /2017-12/Experiment_1/baseline/test01.dat", output)
        self.assertIn("size:       446", output)
        self.assertIn("encoding:   application/octet-stream", output)
        self.assertIn("pid:        ", output)
        self.assertIn("modified:   ", output)
        self.assertIn("frozen:     ", output)

        print("Retrieve folder info from frozen area")
        cmd = "%s info %s -f /2017-12/Experiment_1/baseline" % (self.cli, self.args)
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertIn("project:    %s" % self.project_name, output)
        self.assertIn("area:       frozen", output)
        self.assertIn("type:       folder", output)
        self.assertIn("pathname:   /2017-12/Experiment_1/baseline", output)
        self.assertIn("size:       11297", output)
        self.assertIn("contents:", output)
        self.assertIn("  /2017-12/Experiment_1/baseline/test01.dat", output)
        self.assertIn("  /2017-12/Experiment_1/baseline/test02.dat", output)
        self.assertIn("  /2017-12/Experiment_1/baseline/test03.dat", output)
        self.assertIn("  /2017-12/Experiment_1/baseline/test04.dat", output)
        self.assertIn("  /2017-12/Experiment_1/baseline/test05.dat", output)
        self.assertIn("  /2017-12/Experiment_1/baseline/zero_size_file", output)
        self.assertNotIn(":href>", output)

        print("Attempt to retrieve file info from staging area using invalid target pathname")
        cmd = "%s info %s /no/such/file.txt" % (self.cli, self.args)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: Specified target not found.", output)
        self.assertTrue(failed, output)

        print("Attempt to retrieve folder info from staging area using invalid target pathname")
        cmd = "%s info %s /no/such/folder" % (self.cli, self.args)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: Specified target not found.", output)
        self.assertTrue(failed, output)

        print("Attempt to retrieve file info from frozen area using invalid target pathname")
        cmd = "%s info %s -f /no/such/file.txt" % (self.cli, self.args)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: Specified target not found.", output)
        self.assertTrue(failed, output)

        print("Attempt to retrieve folder info from frozen area using invalid target pathname")
        cmd = "%s info %s -f /no/such/folder" % (self.cli, self.args)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: Specified target not found.", output)
        self.assertTrue(failed, output)

        print("--- Locking and Scope Collisions")

        # NOTE: It is sufficient to simply use service locking for testing all CLI behavior
        # related to lock and scope collision, without having to simulate any initiating
        # actions and test actual pathname collisions. This is because the behavioral tests
        # for the scope collision functionality already cover actual collision use cases,
        # and all that must be checked here is that the CLI script queries the checkScope API
        # endpoint before each relevant operation and exits with an error if a 409 response
        # is received. It doesn't matter whether the 409 response is due to the service being
        # locked or an actual pathname collision.

        print("Lock service")
        response = requests.post("%s/lock/all" % (self.api), auth=self.admin_user, verify=False)
        self.assertEqual(response.status_code, 200)

        print("Verify that service is locked")
        response = requests.get("%s/lock/all" % (self.api), auth=self.test_user, verify=False)
        self.assertEqual(response.status_code, 200)

        print("Attempt to upload file while service is locked")
        cmd = "%s upload %s /2017-08/Experiment_1/test01.dat %s/2017-08/Experiment_1/test01.dat" % (self.cli, self.args, self.testdata)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: Specified target conflicts with an ongoing action.", output)
        self.assertTrue(failed, output)

        print("Attempt to rename file while service is locked")
        cmd = "%s move %s /2017-08/Experiment_1/test01b.dat %s/2017-08/Experiment_1/test01.dat" % (self.cli, self.args, self.testdata)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: Specified target conflicts with an ongoing action.", output)
        self.assertTrue(failed, output)

        print("Attempt to delete file while service is locked")
        cmd = "%s delete %s /2017-08/Experiment_1/test01.dat" % (self.cli, self.args)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: Specified target conflicts with an ongoing action.", output)
        self.assertTrue(failed, output)

        print("Attempt to upload folder while service is locked")
        cmd = "%s upload %s /2017-08/Experiment_1/baseline6 %s/2017-08/Experiment_2/baseline" % (self.cli, self.args, self.testdata)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: Specified target conflicts with an ongoing action.", output)
        self.assertTrue(failed, output)

        print("Attempt to rename folder while service is locked")
        cmd = "%s move %s /2017-08/Experiment_1 /2017-08/Experiment_9" % (self.cli, self.args)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: Specified target conflicts with an ongoing action.", output)
        self.assertTrue(failed, output)

        print("Attempt to delete folder while service is locked")
        cmd = "%s delete %s /2017-08/Experiment_1" % (self.cli, self.args)
        failed = False
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode(sys.stdout.encoding)
            self.assertIn("Error: Specified target conflicts with an ongoing action.", output)
        self.assertTrue(failed, output)

        print("Unlock service")
        response = requests.delete("%s/lock/all" % (self.api), auth=self.admin_user, verify=False)
        self.assertEqual(response.status_code, 200)

        print("Verify that service is unlocked")
        response = requests.get("%s/lock/all" % (self.api), auth=self.admin_user, verify=False)
        self.assertEqual(response.status_code, 404)

        # TODO: Add tests for .netrc usage

        self.success = True
