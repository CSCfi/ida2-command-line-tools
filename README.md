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
v2 of the [IDA service](http://openscience.fi/ida) from the command line.

    Usage: ida [-h]
           ida upload   [-v] [-c config] [-i ignore] [-t host] [-p project] target_pathname local_pathname
           ida download [-v] [-c config]             [-t host] [-p project] target_pathname local_pathname
           ida move     [-v] [-c config]             [-t host] [-p project] target_pathname new_target_pathname
           ida delete   [-v] [-c config]             [-t host] [-p project] target_pathname
           
           -h : show this guide
           -v : provide verbose output
           -c : configuration file
           -i : ignore file
           -t : target host (default: "https://ida.fairdata.fi")
           -p : project name

Pathnames may correspond to either files or folders, except for `download`, where only files may be specified.
If a folder is specified, then the action is performed for all files within that folder and all subfolders.
Actions can be performed on only one file or folder at a time. 

`target_pathname` and `new_target_pathname` are relative to the staging area of the specified project. When
downloading, the `target_pathname` must correspond to a file, as only individual files may be downloaded.
           
`local_pathname` is the pathname of a folder or file on the local system which is to be uploaded, or the
pathname on the local system to which a file will be downloaded. Existing files will not be overwritten.
           
`move` can also be used to rename a file or folder without changing its location.

## Installation
Download the `ida` script, ideally placing it in a location somewhere in your `$PATH`, and ensure that
the script is executable:

    chmod +x ida
    
The `ida` script requires that `bash` is installed on your system as `/bin/bash` and that `curl` is installed
on your system somewhere in your `$PATH`.

## Configuration
The `ida` script requires that certain parameters are defined,
either via environment variables or provided as arguments.

### Configuration file
The `ida` script will look for and load a file `.ida-config` if it exists in your home directory.

You can copy the provided example `ida-config` file from the `examples` subdirectory to your home directory
as `.ida-config` and edit it accordingly.

It is also possible to explicitly specify a configuration file using the `-c` command line option.

Configuration settings will be taken from existing environment variables, followed by `$HOME/.ida-config`,
followed by a configuration file specified with the `-c` command line option, followed by any other
specified command line options; thus, it is possible to partially or completely override configuration
settings defined at each subsequent level of specification.

### Project
You may define the name of your project using the `IDA_PROJECT` environment variable.

    IDA_PROJECT="myproject"
    
You may also specify the project using the `-p` command line option.

If you belong to more than one project, you can define 
whichever project is most frequently used and use the `-p` commmand line option to
explicitly specify another project when different from the default.

All target pathnames are considered to be relative to the staging or frozen area of the specified project.

### IDA Host

The `IDA_HOST` environment variable may be defined as something other than the main
production service, when appropriate. If undefined, the script will default to the 
main production service.

    IDA_HOST="https://ida.fairdata.fi"
            
## Authentication
The `ida` script will need to be provided your IDA account credentials in order to access the project space.

The username and password credentials are the same as you use to log in to the IDA web UI, and are managed in
the [SUI CSC Customer Portal](https://sui.csc.fi/).

Account credentials should ideally be defined using [netrc](https://ec.haxx.se/usingcurl-netrc.html).

You can copy the provided example `netrc` file from the `examples` subdirectory to your home directory
as `.ida-config` and edit it accordingly. Be sure to set the permissions of your netrc file securely:

    chmod go-rwx $HOME/.netrc
    
If a `.netrc` file exists in your home directory, the script will retrieve your credentials from there. 
If no `.netrc` file exists in your home directory, you will be prompted to enter your credentials on each invocation.

## Ignore file
The `ida` script will look for and use a file `.ida-ignore` if it exists in your home directory, to exclude
files matching certain patterns from upload.

This is useful when uploading entire folders, to exclude special system files such as `.DS_Store` on OS-X or
various temporary or log files which might exist within the local filesystem but are not part of the data to
be stored in IDA.

You can copy the provided example `ida-ignore` file from the `examples` subdirectory to your home directory
as `.ida-ignore` and edit it accordingly.

It is also possible to explicitly specify an ignore file using the `-i` command line option.

The ignore file should contain one pattern per line, and will be applied only to filenames, not to pathnames
or portions of pathnames. Patterns should be compatible with those understood by the `-name` option of the
POSIX `find` command.

## Special Notes

Note that files are not officially stored persistently in the IDA service
until they are [frozen](https://openscience.fi/ida-user-guide#project-data-storage),
which can only be done using the web UI of the service.

