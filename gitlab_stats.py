import csv
import gitlab

# !!! DO NOT COMMIT TOKENS !!!
PERSONAL_ACCESS_TOKEN = "<token>"


def get_catma6_basic_project_statistics():
    gl = gitlab.Gitlab(url='https://git.catma.de', private_token=PERSONAL_ACCESS_TOKEN)

    with open('project_stats.csv', 'w', newline='') as csvfile:
        fieldnames = ['id', 'name', 'web_url', 'parent_id', 'created_at', 'storage_size', 'repository_size',
                      'member_count', 'owner_count', 'maintainer_count', 'developer_count', 'reporter_count',
                      'guest_count']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        groups = gl.groups.list(iterator=True, statistics=True, order_by="id")
        for group in groups:
            print(f"Processing group with ID: {group.id}")

            csv_entry = {
                'id': group.id,
                'name': group.name,
                'web_url': group.web_url,
                'parent_id': group.parent_id,
                'created_at': group.created_at
            }

            # these are only available when the token used belongs to an admin
            if hasattr(group, 'statistics'):
                csv_entry['storage_size'] = group.statistics['storage_size']
                csv_entry['repository_size'] = group.statistics['repository_size']

            group_members = group.members.list(get_all=True)

            csv_entry['member_count'] = len(group_members)
            csv_entry['owner_count'] = len([gm for gm in group_members if gm.access_level == 50])
            csv_entry['maintainer_count'] = len([gm for gm in group_members if gm.access_level == 40])
            csv_entry['developer_count'] = len([gm for gm in group_members if gm.access_level == 30])
            csv_entry['reporter_count'] = len([gm for gm in group_members if gm.access_level == 20])
            csv_entry['guest_count'] = len([gm for gm in group_members if gm.access_level == 10])

            writer.writerow(csv_entry)
