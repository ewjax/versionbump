import re
import argparse

import config
import util

# command line arguments stored here
args = argparse.Namespace()


#
#
def increment(value: str) -> str:
    """
    Perform increment operation on string representation of a value, such as what would be obtained from an ini file

    Args:
        value: value to be incremented, e.g. '3' becomes '4'

    Returns:
        string representation of incremented value

    """
    rv = None
    if value.isdecimal():
        rv = f'{int(value) + 1}'
    return rv


#
#
def bump(fieldname: str = None) -> dict:
    """
    Bump operation, to
        - 'auto' fields are incremented by 1
        - increase indicated fieldname by 1, and reset all lower fields (as defined in reset_order) to 0

    Args:
        fieldname: fieldname to be incremented, or 'None' to only increment 'auto' fields

    Returns:
        updated dictionary of {key:val} where keys = fieldnames, val = field value

    """
    reset_order = config.config_data['bump']['reset_order']
    reset_list = reset_order.split(', ')

    # get current version info from config file
    current_version_dict = config.config_data['current_version']

    # make a copy for modification
    new_version_dict = {}
    for key in current_version_dict.keys():
        new_version_dict[key] = current_version_dict[key]

    # to help with the reset logic later, create a dictionary of (k:v) of (fieldnames:reset_order)
    # the logic being, if we are going to bump field at index N, then all fields at index >N will reset to 0
    reset_dict = {}
    i = 0
    for field in reset_list:
        reset_dict[field] = i
        i += 1

    # start by incrementing all fields in bump.auto list
    auto_list = config.config_data['bump']['auto'].split(', ')
    for field in auto_list:
        if field in new_version_dict:
            cur_value = new_version_dict[field]
            new_value = increment(cur_value)
            if new_value:
                new_version_dict[field] = new_value

    # then bumping the requested field
    # note that if the requested field has already been bumped in the auto_list, don't bump it again
    if fieldname in new_version_dict and fieldname not in auto_list:
        cur_value = new_version_dict[fieldname]
        new_value = increment(cur_value)
        if new_value:
            new_version_dict[fieldname] = new_value

            # if we successfully bumped the requested field, now reset all downstream fields, as defined in
            # the [bump][reset_order] value of the ini file
            if fieldname in reset_dict:
                for key in reset_dict.keys():
                    # use the reset_dict dictionary we created earlier to determine if each field should be reset
                    if reset_dict[key] > reset_dict[fieldname]:
                        new_version_dict[key] = '0'

    return new_version_dict


#
#
def version(write_pattern: str, version_dict: dict) -> str:
    """
    create version string, using the f-string pattern in write_pattern, and field values are from the version_dict

    TODO note that a field present in the write_pattern, but not in the list of fields in version_dict,
    will cause an exception which we don't catch, because there is no graceful recovery

    Args:
        write_pattern: f-string format for the created string
        version_dict: dictionary of {key:val} where keys = fieldnames, val = field value

    Returns:
        string containing current version, in write_pattern format

    """

    # use **kwargs formatting to translate fieldnames into the write_pattern
    rv = write_pattern.format(**version_dict)
    return rv


#
#
def write():

    if not args.quiet:
        print(f'Updating output files, format [{args.write}]')

    # get the list of output filenames from the ini file
    write_files = config.config_data['write']['files']
    write_file_list = write_files.split(', ')

    # walk the list of files
    for filename in write_file_list:
        if not args.quiet:
            print(f'-----------------Processing file: [{filename}]--------------------')

        try:
            # read entire contents of file into a list
            with open(filename, 'r') as f:
                line_list = f.readlines()

            # todo delete this line
            print(line_list)

            # walk the list of lines, looking for version strings
            lines_modified = 0
            for ndx, line in enumerate(line_list):

                # parse each line for the presence of a version string
                newline = parse(line)
                if newline:
                    # replace the original line in the list with the new one
                    line_list.pop(ndx)
                    line_list.insert(ndx, newline)

                    # increment the lines modified counter
                    lines_modified += 1

            # todo delete this line
            print(line_list)

            # show how many lines were modified
            if not args.quiet:
                print(f'Lines modified: {lines_modified}')

            # if not dryrun, write out results
            # todo save prev files as .bak versions??


        except FileNotFoundError as fnf:
            if not args.quiet:
                print(fnf)

        # rename filename to filename.bak
        #
        # lines_modified=0
        # read each line from filename.bak
        #   if contains version regex
        #       update line with new version, in either dev or prod format
        #       write updated line to filename
        #       increment lines_modified
        #   else
        #       write original line to filename
        #
        # if successful, then delete filename.bak
        # print status


#
#
def parse(line):

    # set up the read pattern
    regex = config.config_data['syntax']['read_regex']
    pre_regex = '(?P<pre>.*)'
    post_regex = '(?P<post>.*)'
    full_regex = pre_regex + regex + post_regex

    # set up the write pattern
    if args.write == 'dev':
        key = 'write_dev'
    elif args.write == 'prod':
        key = 'write_prod'
    else:
        key = 'write_dev'

    write_pattern = config.config_data['syntax'][key]
    pre_pattern = '{pre}'
    post_pattern = '{post}'
    full_pattern = pre_pattern + write_pattern + post_pattern

    # default return value
    rv = None

    # check this line for presence of a version string
    m = re.match(full_regex, line)
    if m:
        pre_value = m.group('pre')
        post_value = m.group('post')

        # get current version dictionary, and add the pre and post values to it
        version_dict = config.config_data['current_version']
        version_dict['pre'] = pre_value
        version_dict['post'] = post_value

        # use the **kwargs format to smerge together the f-string write pattern with the dictionary of field values
        newline = full_pattern.format(**version_dict)
        # print(f'Original:   {line}')
        # print(f'Revised:    {newline}')
        # print(newline)

        # update the return value
        rv = newline + '\n'

    # return value
    return rv


#
#
def main():

    # *********************************************************************************************************
    # parse the command line
    cli_parser = argparse.ArgumentParser(description=f'Command line tool to automate version bumping. '
                                                     f'Current version maintained in [{config.ini_filename}]')

    # report current version
    cli_parser.add_argument('-c', '--current-version',
                            help=f"return current version string in 'dev' [default] or 'prod' format (development/production)",
                            nargs='?', type=str, const='dev', choices=['dev', 'prod'])

    # bump commands
    cli_parser.add_argument('-b', '--bump',
                            help=f'bump the indicated field [default = auto field(s)].  Reads and writes only [{config.ini_filename}]',
                            nargs='?', type=str, const='auto')

    # write current version to output files
    cli_parser.add_argument('-w', '--write',
                            help=f"Reads version from [{config.ini_filename}], writes in 'dev' [default] or 'prod' format to [write] output files",
                            nargs='?', type=str, const='dev', choices=['dev', 'prod'])

    # dry run?
    cli_parser.add_argument('-d', '--dry-run',
                            help='flag: report what actions will be taken, but do not actually take them',
                            action='store_true')

    # quiet
    cli_parser.add_argument('-q', '--quiet',
                            help='flag: perform all actions with no screen reports',
                            action='store_true')

    # init
    cli_parser.add_argument('-i', '--init',
                            help='flag: print sample config files to screen (stdout), suitable for subsequent redirection and editing',
                            action='store_true')

    # parse the command line
    global args
    args = cli_parser.parse_args()
    if not args.quiet:
        print(args)

    # *********************************************************************************************************

    # load the ini file
    config.load()

    # make a copy of the version info dictionary
    new_version_dict = {}
    current_version_dict = config.config_data['current_version']
    for key in current_version_dict.keys():
        new_version_dict[key] = current_version_dict[key]

    # *********************************************************************************************************

    # process init command and exit
    if args.init:
        if not args.quiet:
            util.print_example_files()
        exit(0)

    # process version command
    if args.current_version:

        # it is a bit amazing that this works.  Handy that format() is written to properly deal with **kwargs, which as it happens,
        # the dictionary representation of the config.config objects are in exactly the right format to support
        write_dev = config.config_data['syntax']['write_dev']
        write_prod = config.config_data['syntax']['write_prod']

        if args.current_version == 'dev':
            if not args.quiet:
                print(f'Current version (dev format):   {version(write_dev, current_version_dict)}')
        elif args.current_version == 'prod':
            if not args.quiet:
                print(f'Current version (prod format):  {version(write_prod, current_version_dict)}')

    # process bump command
    if args.bump:

        # current_version_dict = config.config_data['current_version']
        write_dev = config.config_data['syntax']['write_dev']

        # determine which fieldname to bump
        fieldname = None
        if args.bump in current_version_dict.keys():
            fieldname = args.bump
        else:
            if args.bump != 'auto' and not args.quiet:
                print(f"    ['{args.bump}'] unrecognized field name")
                print(f'    Valid field names: {list(current_version_dict.keys())}')

        # do the bump and report what new version will be
        new_version_dict = bump(fieldname)
        if not args.quiet:
            print(f'Current version (dev format): {version(write_dev, current_version_dict)}')
            print(f'New version     (dev format): {version(write_dev, new_version_dict)}')

        # if any fields have changed, then save them back to the current dictionary, and write it to disk
        if args.dry_run is False:
            modified = False
            for fieldname in current_version_dict.keys():
                new_val = new_version_dict[fieldname]
                current_val = current_version_dict[fieldname]
                if new_val != current_val:
                    config.config_data['current_version'][fieldname] = new_val
                    modified = True

            if modified:
                config.save()
                if not args.quiet:
                    print(f'Updated version info saved to ini file [{config.ini_filename}]')

    # process write command
    if args.write:
        write()


if __name__ == '__main__':
    main()
