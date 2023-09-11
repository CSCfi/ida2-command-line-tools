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

# IDA Command Line Tools

This repository provides a [bash](https://www.gnu.org/software/bash/) script `ida` for interacting with
the [Fairdata IDA service](https://www.fairdata.fi/en/ida/) from the command line.

The script should execute correctly on any Unix like system; including Linux, BSD, Mac OS-X, and Windows
Subsystem for Linux (WSL).

See the installation and configuration instructions below.

    Usage: ida [-h]
           ida upload    [-v|V] [-D] [-F] [-c config] [-i ignore] [-t host] [-p project]      target_pathname local_pathname
           ida copy      [-v|V] [-D]      [-c config]             [-t host] [-p project] [-f] target_pathname new_target_pathname
           ida move      [-v|V] [-D]      [-c config]             [-t host] [-p project]      target_pathname new_target_pathname
           ida delete    [-v|V] [-D]      [-c config]             [-t host] [-p project]      target_pathname
           ida download  [-v|V]           [-c config]             [-t host] [-p project] [-f] target_pathname local_pathname
           ida validate  [-v|V]           [-c config]             [-t host] [-p project] [-f] target_pathname local_pathname
           ida info      [-v|V]      [-j] [-c config]             [-t host] [-p project] [-f] target_pathname
           ida inventory [-v|V]           [-c config]             [-t host] [-p project]

           -h : show this guide
           -p : project name
           -t : target host (default: "https://ida.fairdata.fi")
           -f : target_pathname is relative to frozen area, new_target_pathname is relative to staging area
           -c : configuration file
           -i : ignore file
           -v : provide verbose output
           -V : provide both verbose and debug output with explicit details about configuration and all operations
           -D : dry-run (does not perform any operations with changes in the IDA service)
           -F : force upload (upload files even when the local file already exists in the service)
           -j : format the output of the info action as JSON

Pathnames may correspond to either files or folders. If a folder is specified, then the action is
performed for all files within that folder and all subfolders. Folders are downloaded as zip files.
Actions can be performed on only one file or folder at a time.

Unless the -f parameter is specified, `target_pathname` and `new_target_pathname` are relative to the
staging area of the specified project. If the -f parameter is specified, then the `target_pathname` is
relative to the frozen area; and if the `copy` action is specified, the `new_target_pathname` is relative
to the staging area of the specified project. The -f parameter is **only** allowed for `download`, `copy`,
`validate`, and `info` actions.

`local_pathname` is the pathname of a folder or file on the local system which is to be uploaded, or the
pathname on the local system to which a file will be downloaded (either a single data file or the zip
file for a data folder). Existing files will not be overwritten.

The `move` action can also be used to rename a file or folder without changing its location.

If both the -v (verbose) and the -D (dry-run) parameters are specified, then verbose status messages
for operations which are skipped will be prefixed with an asterisk '*' indicating that they were not
actually performed.

Note that files are not officially stored persistently in the IDA service until they are frozen, which can
only be done using the web UI of the service (https://www.fairdata.fi/en/ida/user-guide/#project-data-storage).

The output format of the info action is plain text with indentation, unless the -j (JSON) flag is given.
The output format of the inventory action is always formatted as JSON.

Examples are provided at the end of this guide.

## Installation

The `ida` and `ida-checksum` scripts requires that `bash` is installed on your system as `/bin/bash` and that
the utilities `curl`, `xargs`, `awk`, and `sha256sum` (or `shasum` on Mac OS-X) are installed on your system
and visible somewhere in your `$PATH`.

Download the `ida` and `ida-checksum` scripts, ideally placing them in a location somewhere in your `$PATH`,
and ensure that the scripts are executable. E.g.:

    curl -LJO "https://raw.githubusercontent.com/CSCfi/ida2-command-line-tools/master/ida"
    curl -LJO "https://raw.githubusercontent.com/CSCfi/ida2-command-line-tools/master/ida-checksum"
    chmod +x ida ida-checksum

## Authentication

The `ida` script must be provided with valid IDA account credentials in order to access the project space.

The username will be your CSC account username, as managed in the CSC Customer Portal [MyCSC](https://my.csc.fi/).

The password will be an application password that you create in the IDA service, as detailed below.

### Application passwords

To create an application password, log in to the IDA web UI, and open the settings view by selecting "Personal"
from the pull down settings menu at the top right of the view, and then either select the "Security" section
in the left hand navigation pane or scroll down to the security section.

In the field provided, enter a name for your new application password and click "Create new app password". The
new application password will be displayed, and must be copied and saved immediately. It will not be possible to
view the application password again, though it will be listed by the provided name and you will be able to delete
it and remove it from use.

## Configuration

The `ida` script requires that certain parameters are defined, either via environment variables, or
via a configuration file, or provided via command line arguments.

### Configuration file

The `ida` script will look for and load a file `$HOME/.ida-config` if it exists in your home directory.

You can copy the provided example `ida-config` file from the `templates` subdirectory to your home directory
as `$HOME/.ida-config` and edit it accordingly. E.g.:

    curl -LJ "https://raw.githubusercontent.com/CSCfi/ida2-command-line-tools/master/templates/ida-config" -o $HOME/.ida-config

Be sure to set the permissions of your configuration file securely so its contents are not visible to others:

    chmod go-rwx $HOME/.ida-config

It is also possible to explicitly specify a configuration file using the `-c` command line option:

    -c /some/path/name/to/ida-config

Configuration settings will be taken from existing environment variables, followed by `$HOME/.ida-config`,
followed by a configuration file specified with the `-c` command line option, followed by any other
specified command line options; thus, it is possible to partially or completely override configuration
settings defined at each subsequent level of specification.

### Target Host

You may define the target host using the `IDA_HOST` environment variable, when appropriate. If undefined,
all commands will be directed to the production service `https://ida.fairdata.fi`.

For example, if you want all commands to be directed to the IDA demo environment host
`https://ida.demo.fairdata.fi` you would define it as follows:

    IDA_HOST="https://ida.demo.fairdata.fi"

You may also specify the target host using the `-t` command line option:

    -t "https://ida.demo.fairdata.fi"

### Project

You may define your project using the `IDA_PROJECT` environment variable, specifying the CSC project number.

For example, if your project's CSC project number were "2100123" you would define it as follows:

    IDA_PROJECT="2100123"

You may also specify the CSC project number using the `-p` command line option:

    -p "2100123"

If you belong to more than one project, you can define whichever project is most frequently used and
use the `-p` commmand line option to explicitly specify another project when different from the default.

All target pathnames are considered to be relative to the staging or frozen area of the specified project.

### Username

You may define your CSC username using the `IDA_USERNAME` environment variable.

For example, if your CSC username were "johndoe" you would define it as follows:

    IDA_USERNAME="johndoe"

### Password

You may define your IDA application password using the `IDA_PASSWORD` environment variable.

For example, if your IDA application password were "Wre-xoZyN-d4dWc-RStwi-36d2t" you would define it as follows:

    IDA_PASSWORD="Wre-xoZyN-d4dWc-RStwi-36d2t"

### Netrc

For added security, account credentials (username and password) can be defined for each
target host using [netrc](https://ec.haxx.se/usingcurl-netrc.html) in a `$HOME/.netrc` file
located in your home directory:

    machine ida.fairdata.fi login johndoe password Wre-xoZyN-d4dWc-RStwi-36d2t

If account credentials are defined using netrc, it will not be necessary to define either `IDA_USERNAME` or
`IDA_PASSWORD` elsewhere.

You can copy the provided example `netrc` file from the `templates` subdirectory to your home directory
as `$HOME/.netrc` and edit it accordingly.

Be sure to set the permissions of your configuration file securely so its contents are not visible to others:

    chmod go-rwx $HOME/.netrc

### Run-time authentication

If any account credentials (username and/or password) cannot be found from any of the above
sources, you will be prompted to enter them for each command.

## Ignore file

The `ida` script will look for and use a file `.ida-ignore` if it exists in your home directory, to exclude
files matching certain patterns from upload.

This is useful when uploading entire folders, to exclude special system files such as `.DS_Store` on MacOSX or
various temporary or log files which might exist within the local filesystem but are not part of the data to
be stored in IDA.

You can copy the provided example `ida-ignore` file from the `templates` subdirectory to your home directory
as `$HOME/.ida-ignore` and edit it accordingly.

The ignore file should contain one pattern per line, and will be applied only to filenames, not to pathnames
or portions of pathnames. Patterns should be compatible with those understood by the `-name` option of the
POSIX `find` command.

It is also possible to explicitly specify an ignore file using the `-i` command line option:

    -i /some/path/name/to/ida-ignore

## Collision Avoidance for File Operations

All users belonging to a given project have the same rights, and may interact with, add, and remove
project data concurrently. To help avoid one user unintentionally interfering with another user's
activity, the IDA service employs a number of checks and restrictions to ensure that multiple concurrent
users' activities do not collide in undesirable ways.

Operations on files in the staging area, including uploading, deleting, renaming, and moving (but not
downloading), will not be allowed if they intersect with the scope of an action that is being initiated.

If an action is initiated in the web UI of the service, it takes precidence over any batch operations
utilizing the command line tools, such that the batch operations may be blocked by the initiated action.
In such cases, the command line tools will exit with an error message.

More details can be found in the [online user guide](https://www.fairdata.fi/en/ida/user-guide#collision-avoidance).

## Info Output

The output of the `info` action is both human friendly as well as easily parsable by script.

### File Info

File info consists of a sequence of field::value pairs, one per line, with the field name
followed by a colon ":" and padded by one or more spaces. E.g.

    project:    12345
    pathname:   /2017-08/Experiment_1/test01.dat
    area:       frozen
    type:       file
    pid:        5c41b5d90561a361661419f75150
    size:       446
    checksum:   sha256:56293a80e0394d252e995f2debccea8223e4b5b2b150bee212729b3b39ac4d46
    encoding:   application/octet-stream
    modified:   2017-01-03T19:27:42Z
    frozen:     2017-01-18T11:17:15Z

Fields included for all files, in either the staging or frozen areas:

* project
* pathname
* area
* type
* size (in bytes)
* encoding
* checksum (not always available, see note below)
* modified

Additional fields provided for all files in the frozen area:

* pid
* frozen

Note: The checksum for a file is not always available, either because a file in staging was
not uploaded using a recent version of the IDA command line tools and/or postprocessing is
still ongoing for the freeze action with which a frozen file is associated. If the file is
frozen and no checksum is included in the output of the info action, check the pending actions
section of the IDA service web UI to monitor the status of the relevant pending action.

### Folder Info

Folder info consists of a sequence of field::value pairs, one per line, with the field name followed
by a colon ":" and padded by one or more spaces. Field::value pair lines are
followed by a heading "contents:" on its own line, followed
by zero or more pathnames, one per line, corresponding to the files or folders contained within the specified
folder. E.g.

    project:    12345
    pathname:   /2017-08/Experiment_1
    area:       staging
    type:       folder
    size:       23040
    contents:
      /2017-08/Experiment_1/test01.dat
      /2017-08/Experiment_1/test02.dat
      /2017-08/Experiment_1/test03.dat
      /2017-08/Experiment_1/test04.dat
      /2017-08/Experiment_1/test05.dat
      /2017-08/Experiment_1/baseline/

Each pathname is indented with whitespace, and thereby easily distinguished from lines with field::value pairs,
where the field name begins at the start of each line.

Folder pathnames end in a forward slash "/", and thereby easily distinguished from file pathnames, which never
end in a forward slash.

Empty folders will have no output lines following the "contents:" heading.

To retrieve a listing of the root contents of either the staging or frozen area for a project, the target
pathname "/" can be specified.

Fields included for all folders, in either the staging or frozen areas:

* project
* pathname
* area
* type
* size (in bytes)
* contents

### File Inventory

The output of the `inventory` action is encoded as a JSON object with the following example structure:

    {
        "project": "12345",
        "created": "2020-03-13T12:58:36Z",
        "totalFiles": 83,
        "totalStagedFiles": 45,
        "totalFrozenFiles": 38,
        "staging": {
            "/2017-08/Experiment_2/test01.dat": {
                "size": 1234,
                "modified": "2020-02-11T14:04:26Z"
            },
            ...
        },
        "frozen": {
            "/2017-08/Experiment_1/test02.dat": {
                "size": 4567,
                "modified": "2020-02-11T14:04:26Z",
                "pid": "5e4ea9a829bfe465487185f441180",
                "checksum": "sha256:b5bb9d8014a0f9b1d61e21e796d78dccdf1352f23cd32812f4850b878ae4944c",
                "frozen": "2020-02-20T15:07:32Z"
            },
            ...
        }
    }

## Validation

The `validate` action can be used to check whether local files exist in IDA and have the same size in bytes in
both locations.

The target and local pathnames can correspond either to an individual file or a directory scope for which all
files within that scope will be checked. If the -f (frozen) parameter is given, local files will be compared
against files in the frozen area; else they will be compared against files in staging.

Normally, only files that are missing from IDA or have a different size are reported, but if the -v (verbose)
parameter is given, the status of all files will be reported.

Files within a directory scope which exist in IDA but which are not present locally will be ignored.

## Local File Checksum Generation

The included utility `ida-checksum` can be used to generate a checksum for a local file, of the same
format (SHA-256, lowercase) used by the IDA service.

    Usage: ida-checksum -h
           ida-checksum local_pathname

## Special Notes

Files named `.htaccess` and files with a suffix of either `.part` or `.filepart` may not be uploaded.
The filenames will need to be changed in some manner, such as zipping the file or adding some other
suffix or name change. These restrictions are due to security and other internal management contraints
of the underlying Nextcloud platform employed by the IDA service.

Note that files are not officially stored persistently in the IDA service
until they are [frozen](https://www.fairdata.fi/en/ida/user-guide/#project-data-storage),
which can only be done using the web UI of the service.

## Examples

For the following examples, it is assumed that the user has defined their primary project in their
`.ida-config` file and their account credentials in their `.netrc` file.

Note that when uploading, copying or moving files or folders, complete target pathnames in the project staging area must
always be specified, not merely the pathname of the folder into which data will be uploaded or moved.

**Upload a local folder named "run42" to the staging area with the relative pathname "/2017-04/Experiment_42":**

    ida upload /2017-04/Experiment_42 run42

**Perform the same upload as above, with verbose output detailing all operations, and appending (saving) the output (including error output) to the local file "./uploads.log":**

    ida upload -v /2017-04/Experiment_42 run42 2>&1 | tee -a ./uploads.log

**Upload a local file named "run42/test66.dat" to the staging area with the relative pathname "/2017-04/Experiment_42/test66.dat":**

    ida upload /2017-04/Experiment_42/test66.dat run42/test66.dat

**Download a folder from the staging area with the relative pathname "/2017-04/Experiment_42" to the local file "run42.zip":**

    ida download /2017-04/Experiment_42 run42.zip

**Download a folder from the frozen area with the relative pathname "/2017-04/Experiment_42" to the local file "run42.zip":**

    ida download -f /2017-04/Experiment_42 run42.zip

**Download a file from the staging area with the relative pathname "/2017-04/Experiment_42/test66.dat" to the local pathname "run42/test66.dat":**

    ida download /2017-04/Experiment_42/test66.dat run42/test66.dat

**Download a file from the frozen area with the relative pathname "/2017-04/Experiment_42/test66.dat" to the local pathname "run42/test66.dat":**

    ida download -f /2017-04/Experiment_42/test66.dat run42/test66.dat

**Rename (move) a folder in the staging area from "/2017-04/Experiment_42" to "/2017-04/Experiment_42a":**

    ida move /2017-04/Experiment_42 /2017-04/Experiment_42a

**Copy a file in the staging area from "/2017-04/Experiment_42/test66.dat" to "/2017-04/Experiment_42/verified/test66.dat":**

    ida copy /2017-04/Experiment_42/test66.dat /2017-04/Experiment_42/verified/test66.dat

&nbsp;&nbsp;&nbsp;&nbsp;The folder path "/2017-04/Experiment_42/verified" will be created if it does not already exist.

**Copy a file from the frozen area from "/2017-04/Experiment_42/baseline.dat" to the staging area as "/2019-10/Experiment_56/baseline.dat":**

    ida copy -f /2017-04/Experiment_42/baseline.dat /2019-10/Experiment_56/baseline.dat

&nbsp;&nbsp;&nbsp;&nbsp;The folder path "/2019-10/Experiment_56" will be created in the staging area if it does not already exist.

**Move a file in the staging area from "/2017-04/Experiment_42/test66.dat" to "/2017-04/Experiment_42/verified/test66.dat":**

    ida move /2017-04/Experiment_42/test66.dat /2017-04/Experiment_42/verified/test66.dat

&nbsp;&nbsp;&nbsp;&nbsp;The folder path "/2017-04/Experiment_42/verified" will be created if it does not already exist.

**Delete a folder from the staging area with the relative pathname "/2017-04/Experiment_42":**

    ida delete /2017-04/Experiment_42

**Delete a file from the staging area with the relative pathname "/2017-04/Experiment_42/test66.dat":**

    ida delete /2017-04/Experiment_42/test66.dat

**Retrieve info about a folder in the staging area with the relative pathname "/2017-04/Experiment_42":**

    ida info /2017-04/Experiment_42

**Retrieve info about a folder in the frozen area with the relative pathname "/2017-04/Experiment_42":**

    ida info -f /2017-04/Experiment_42

**Retrieve info about a file in the staging area with the relative pathname "/2017-04/Experiment_42/test66.dat":**

    ida info /2017-04/Experiment_42/test66.dat

**Retrieve info about a file in the frozen area with the relative pathname "/2017-04/Experiment_42/test66.dat":**

    ida info -f /2017-04/Experiment_42/test66.dat

**Retrieve info about the root of the staging area of the project:**

    ida info /

**Retrieve info about the root of the frozen area of the project:**

    ida info -f /

**Retrieve an inventory of all project files stored in the service:**

    ida inventory

