# Can be used to resolve a common type of conflict in annotation collection page files that occurs when two separate
# users both add new annotations to the same collection. The default Git text merge driver does not deal well with JSON,
# because it is not aware of the logical structure of such a file (neither the bounds of JSON objects nor, in our case,
# the annotation ID are taken into account). In our case there is also quite a lot of repetition between distinct
# annotations, further complicating a simple line-by-line comparison.
#
# Such conflicts can sometimes be resolved quite easily and interactively through the GitLab UI with simple "ours" or
# "theirs" choices, but often require manual editing of the conflicted file (also, no user documentation exists for
# either approach at the time of writing this, so it almost inevitably becomes a support task).
#
# The below function automates the manual conflict resolution task, however BE AWARE THAT IT WILL NOT RESOLVE TRUE
# CONFLICTS, i.e. where different users have modified the SAME annotation, instead writing both versions to the merged
# file and outputting a warning about a mismatch, requiring further manual investigation. Therefore, conflicted files
# should not simply be processed without first being reviewed and/or checked afterwards, and you should check for any
# warnings being printed. This also has not been tested with scenarios where annotations are being deleted at the same
# time (although a test does exist, see tests/test_conflicted_ac_page_resolver.py).
#
# Expected input: a single annotation collection page file (JSON) with conflict markers, as can be fetched from GitLab
#                 by navigating to a blocked merge request, clicking on "Resolve conflicts" and then "Edit inline"
# Output:         files named "our_file", "their_file" and "merged_file", where the first two should match "our" and
#                 "their" version of the file as found in the relevant branches at the time the input file was fetched
#
# TODOs: 1. see below
#        2. investigate writing a custom merge driver, refs:
#           https://gregmicek.com/software-coding/2020/01/13/how-to-write-a-custom-git-merge-driver/
#           https://git-scm.com/docs/gitattributes#_built_in_merge_drivers
#           https://www.google.com/search?q=git+custom+merge+driver

import json
from collections import deque
from datetime import datetime

# HEAD_MARKER = "<<<<<<< HEAD"
HEAD_MARKER = "<<<<<<<"
SEPARATOR = "======="
# MASTER_MARKER = ">>>>>>> master"
MASTER_MARKER = ">>>>>>>"

CATMA_MARKUPTIMESTAMP_UUID = "CATMA_54A5F93F-5333-3F0D-92F7-7BD5930DB9E6"

def resolve(page_file):
    with open(page_file, encoding="utf-8", newline=None) as f:
        lines = f.readlines()

    ours_start = None
    ours_end = None
    theirs_start = None
    theirs_end = None

    unconflicted_start_until_idx = None
    unconflicted_end_from_idx = None
    unconflicted_line_idxs = deque()  # all unconflicted lines that appear between conflicts, TODO: use ranges directly?

    # each element is a 4-tuple containing the start and end line indexes of 'our' and 'their' chunks respectively
    conflicts = []

    next_expected_marker = HEAD_MARKER

    for idx, line in enumerate(lines):
        if line.startswith(HEAD_MARKER) and next_expected_marker == HEAD_MARKER:
            ours_start = idx + 1
            next_expected_marker = SEPARATOR

            if unconflicted_start_until_idx is None:
                unconflicted_start_until_idx = idx  # only set when the first conflict is encountered

            if unconflicted_end_from_idx is not None and unconflicted_end_from_idx < idx:
                unconflicted_line_idxs += list(range(unconflicted_end_from_idx, idx))

            continue
        elif line.startswith(SEPARATOR) and next_expected_marker == SEPARATOR:
            ours_end = idx
            theirs_start = idx + 1
            next_expected_marker = MASTER_MARKER
            continue
        elif line.startswith(MASTER_MARKER) and next_expected_marker == MASTER_MARKER:
            theirs_end = idx
            next_expected_marker = HEAD_MARKER

            unconflicted_end_from_idx = idx + 1  # keep overwriting until there are no more conflicts

            #current_conflict_our_lines = lines[ours_start:ours_end]
            #current_conflict_their_lines = lines[theirs_start:theirs_end]
            conflicts.append((ours_start, ours_end, theirs_start, theirs_end))

            continue
        else:
            # sanity check
            if line.startswith((HEAD_MARKER, SEPARATOR, MASTER_MARKER)) and not line.startswith(next_expected_marker):
                raise f"Expected marker '{next_expected_marker}' but encountered '{line[:-1]}' on line {idx+1}"

    # had the following for ours and theirs first, but it results in nested lists
    # our_file_lines = lines[:unconflicted_start_until] \
    #                  + list(lines[conflict[0]:conflict[1]] for conflict in conflicts) \
    #                  + lines[unconflicted_end_from:]
    # ref: https://stackoverflow.com/a/56407963/207981
    our_file_lines = lines[:unconflicted_start_until_idx]
    their_file_lines = lines[:unconflicted_start_until_idx]
    for conflict in conflicts:
        while len(unconflicted_line_idxs) > 0 and unconflicted_line_idxs[0] < conflict[0]:
            unconflicted_line_idx = unconflicted_line_idxs.popleft()
            our_file_lines += lines[unconflicted_line_idx]
            their_file_lines += lines[unconflicted_line_idx]
        our_file_lines += lines[conflict[0]:conflict[1]]
        their_file_lines += lines[conflict[2]:conflict[3]]
    our_file_lines += lines[unconflicted_end_from_idx:]
    their_file_lines += lines[unconflicted_end_from_idx:]

    with open("our_file", "w+", encoding="utf-8", newline="\n") as our_file, \
            open("their_file", "w+", encoding="utf-8", newline="\n") as their_file:
        our_file.writelines(our_file_lines)
        their_file.writelines(their_file_lines)

        our_file.seek(0)
        their_file.seek(0)

        # TODO: consider fetching the two files directly from GitLab given a link to the blocked merge request,
        #       then feed into the below, or just fetch the conflicted file with the conflict markers
        our_annotations = json.load(our_file)
        their_annotations = json.load(their_file)

    our_annotation_ids = [annotation["id"][-42:] for annotation in our_annotations]
    their_annotation_ids = [annotation["id"][-42:] for annotation in their_annotations]
    their_new_annotation_ids = list(set(their_annotation_ids) - set(our_annotation_ids))
    their_new_annotations = [annotation for annotation in their_annotations \
                             if annotation["id"][-42:] in their_new_annotation_ids]

    # ensure that annotations occurring in both files are equal
    both_annotation_ids = list(set(their_annotation_ids) & set(our_annotation_ids))
    for our_annotation in our_annotations:
        if our_annotation["id"][-42:] not in both_annotation_ids:
            continue

        for their_annotation in their_annotations:
            if their_annotation["id"][-42:] != our_annotation["id"][-42:]:
                continue

            if their_annotation != our_annotation:
                print(f"WARNING: Mismatch in annotations with ID {our_annotation["id"][-42:]}, check manually")
                # append their mismatched annotation to their_new_annotations so that it is written to the merged file
                # for manual investigation
                their_new_annotations += [their_annotation]

    # insert their new annotations in the appropriate place according to timestamps
    our_annotations.reverse()
    for their_new_annotation in their_new_annotations:
        was_added = False

        for idx, our_annotation in enumerate(our_annotations):
            if datetime.fromisoformat(
                    our_annotation["body"]["properties"]["system"][CATMA_MARKUPTIMESTAMP_UUID][0]
            ) <= datetime.fromisoformat(
                their_new_annotation["body"]["properties"]["system"][CATMA_MARKUPTIMESTAMP_UUID][0]
            ):
                our_annotations.insert(idx, their_new_annotation)
                was_added = True
                break
            else:
                if idx == len(our_annotations) - 1:
                    our_annotations.append(their_new_annotation)
                    was_added = True

        if not was_added:
            raise "Failed to add annotation"

    # our_annotations now contains the merged set of annotations
    # reverse it again to put them in the correct chronological order
    our_annotations.reverse()

    with open("merged_file", "w", encoding="utf-8", newline="\n") as merged_file:
        json.dump(our_annotations, merged_file, indent=2)