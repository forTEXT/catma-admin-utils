# Can be used to "copy" CATMA comments (issues) into a different project/repo within GitLab (obviously this only makes
# sense if it's the same document on both sides).
# NB: This doesn't actually fetch the comments from the source project, though it could quite easily be modified to do
# so. At the time of writing, the comments had already been fetched from the source projects manually (using Postman)
# and modified to replace source document IDs with destination document IDs using simple find & replace.
#
# base_dir is expected to contain a subdirectory for each source project (though the directory name is irrelevant).
# Each subdirectory is then expected to contain:
# - a project_ids.json containing a simple mapping from source to destination project ID, eg: {"old":1,"new":2}
#   (note that "old" is not currently used)
# - one or more other JSON files containing the output from /projects/:id/issues
#   (GitLab APIs use pagination, and the maximum page size is 100, so if there are >100 issues it's expected that there
#   will be multiple files, eg: pg1.json, pg2.json, etc.)
#
# Check base_dir, gitlab_api_base_url and gitlab_username_pat_map below

import os
import json
import requests

base_dir = r"/path/to/base/dir"

gitlab_api_base_url = "https://git.catma.de/api/v4"
gitlab_api_project_issues_template = "/projects/{id}/issues"
gitlab_auth_header_key = "PRIVATE-TOKEN"

# Needs to contain a valid personal access token for every issue author found in the source files, as issues are
# re-created using the original authors
gitlab_username_pat_map = {
    # !!! DO NOT COMMIT TOKENS !!!
    "user1": "<token>",
    "user2": "<token>"
    # !!! DO NOT COMMIT TOKENS !!!
}

expected_comment_keys = [
    "title", "description", "created_at", "state", "labels", "author", "user_notes_count", "issue_type"
]


def copy_comments(dry_run=True):
    base_dir_filenames = os.listdir(base_dir)
    dirs = [os.path.join(base_dir, dir) for dir in base_dir_filenames if os.path.isdir(os.path.join(base_dir, dir))]

    for dir in dirs:
        print(f"Now working on {dir}")
        # we expect to find a project_ids.json containing the old and new project IDs (although we only use the new one)
        # we also expect to find at least one other JSON file containing the comments
        filenames = os.listdir(dir)
        assert len(filenames) >= 2
        assert "project_ids.json" in filenames
        filenames.remove("project_ids.json")

        with open(os.path.join(dir, "project_ids.json")) as f:
            file_contents = f.read()
            project_ids = json.loads(file_contents)

            if "new" not in project_ids:
                raise KeyError("Expected key 'new'")

            new_project_id = project_ids.get("new")
            print(f"Found new project ID: {new_project_id}")

        no_of_successful_posts = 0
        no_of_posts_requiring_inspection = 0

        for filename in filenames:
            if not filename.endswith(".json"):
                continue

            print(f"Now processing {filename}")

            with open(os.path.join(dir, filename), encoding="utf-8") as f:
                file_contents = f.read()
                obj = json.loads(file_contents)

                if not isinstance(obj, list):
                    print(f"Expected to find a list of comments, got {type(obj)}, skipping...")
                    continue

                for entry in obj:
                    # do some basic sanity checking
                    skip = False
                    entry_id = entry.get("id")

                    for key in expected_comment_keys:
                        if key not in entry:
                            print(f"Warning: Entry with ID {entry_id} is missing expected key '{key}', skipping")
                            skip = True
                            break

                    labels = entry.get("labels")
                    if not isinstance(labels, list) or len(labels) > 1 or labels[0] != "CATMA Comment":
                        print(f"Warning: Entry with ID {entry_id} doesn't have the expected label, skipping")
                        skip = True

                    if entry.get("user_notes_count") != 0:
                        # notes are issue comments, we don't handle them
                        # (note that one can clone issues with notes, but doing that would mean having to later edit
                        # them to update the document IDs)
                        print(f"Warning: Entry with ID {entry_id} has a non-zero notes count, skipping")
                        skip = True

                    if entry.get("issue_type") != "issue":
                        print(f"Warning: Entry with ID {entry_id} has an unexpected issue_type, skipping")
                        skip = True

                    if entry.get("state") != "opened":
                        print(f"Warning: Entry with ID {entry_id} does not have state 'opened', skipping")
                        skip = True

                    if entry.get("author").get("username") not in gitlab_username_pat_map:
                        print(f"Warning: Entry with ID {entry_id} is missing a corresponding entry in "
                              "gitlab_username_pat_map, skipping")
                        skip = True

                    if skip:
                        continue

                    # looks good, create the new issue / CATMA comment
                    project_issues_url_segment = gitlab_api_project_issues_template.format(id=new_project_id)
                    url = f"{gitlab_api_base_url}{project_issues_url_segment}"

                    data = {
                        "title": entry.get("title"),
                        "description": entry.get("description"),
                        # created_at requires administrator or project/group owner rights. We don't display it anyway.
                        # "created_at":
                        "labels": labels[0],
                    }

                    headers = {
                        gitlab_auth_header_key: gitlab_username_pat_map[entry.get("author").get("username")],
                        "Content-Type": "application/json"
                    }

                    if dry_run:
                        print("dry_run=True, setting to False would post the following data:\n"
                              f"URL: {url}\n"
                              f"data: {data}")
                    else:
                        response = requests.post(url, json=data, headers=headers)

                        if response.status_code == 201:
                            no_of_successful_posts += 1
                        else:
                            no_of_posts_requiring_inspection += 1
                            print(response.status_code)
                            print(response.text)

        print(f"No. of successful posts: {no_of_successful_posts}")
        print(f"No. of posts requiring inspection: {no_of_posts_requiring_inspection}")
