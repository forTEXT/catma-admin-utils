import os
import shutil

import gitlab

# !!! DO NOT COMMIT TOKENS !!!
PERSONAL_ACCESS_TOKEN = "<token>"

LOCALGIT_PATH='/catmadata/localgit'
# projects that will not be touched:
EXCLUSIONS = []


# https://stackoverflow.com/a/234329/207981
def walklevel(some_dir, level=1):
    some_dir = some_dir.rstrip(os.path.sep)
    assert os.path.isdir(some_dir)
    num_sep = some_dir.count(os.path.sep)
    for root, dirs, files in os.walk(some_dir):
        yield root, dirs, files
        num_sep_this = root.count(os.path.sep)
        if num_sep + level <= num_sep_this:
            del dirs[:]


def cleanup_catma6_projects(dry_run=True):
    if dry_run:
        print('dry_run=True, nothing will actually be deleted')

    gl = gitlab.Gitlab(url='https://git.catma.de', private_token=PERSONAL_ACCESS_TOKEN)

    # if python-gitlab < 3.6.0, parameter "get_all" needs to be changed to "all" and "iterator=True" to "as_list=False"
    groups = gl.groups.list(
        get_all=True, iterator=True, per_page=100, order_by="id", top_level_only=True, search="CATMA"
    )
    for group in groups:
        print(f'\nProcessing group "{group.name}" with ID: {group.id}')
        print(f'- Created at: {group.created_at}, web URL: {group.web_url}')

        if group.path in EXCLUSIONS:
            print('Group listed in exclusions, skipping')
            continue

        # if python-gitlab < 3.6.0, parameter "get_all" needs to be changed to "all"
        group_members = group.members.list(get_all=True, per_page=100)

        for member in group_members:
            print(f'-- Member: {member.username}')

            member_localgit_path = os.path.join(LOCALGIT_PATH, member.username)
            if not os.path.exists(member_localgit_path):
                print(f'   No localgit dir found for member "{member.username}", skipping')
                continue

            member_group_path = os.path.join(member_localgit_path, group.path)
            if not os.path.exists(member_group_path):
                print(f'   No group dir found for member "{member.username}" and group "{group.name}", skipping')
                continue

            assert os.path.isdir(member_group_path)
            print(f'   Deleting group dir at {member_group_path} ...')
            if not dry_run:
                shutil.rmtree(member_group_path)

            if not os.listdir(member_localgit_path):
                print(f'   Deleting member localgit dir at {member_localgit_path} as it is now empty ...')
                assert os.path.isdir(member_localgit_path)
                if not dry_run:
                    os.rmdir(member_localgit_path)

        print(f'Deleting group "{group.name}" ...')
        if not dry_run:
            group.delete()

        # scan for group dirs that may still exist (eg: if someone was removed from a project after having opened it at
        # least once)
        for dirpath, dirnames, filenames in walklevel(LOCALGIT_PATH, level=2):
            parent_path, potential_group_dir_name = dirpath.rsplit(os.path.sep, maxsplit=1)
            if potential_group_dir_name == group.path:
                print(f'Found leftover group dir at path {dirpath}, deleting ...')
                if not dry_run:
                    shutil.rmtree(dirpath)

                if not os.listdir(parent_path):
                    print(f'- Deleting member localgit dir at {parent_path} as it is now empty ...')
                    assert os.path.isdir(parent_path)
                    if not dry_run:
                        os.rmdir(parent_path)
