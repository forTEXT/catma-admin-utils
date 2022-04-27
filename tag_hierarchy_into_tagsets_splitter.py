# Can be used to turn a tag hierarchy contained in a TEI-XML file into multiple tagsets and write these into a new
# TEI-XML file.
#
# The expectation is that the input file contains a single tagset and that only some tag-trees (top-level tags and their
# children) should be considered, their sub-trees being turned into individual, proper tagsets.
# Provision is also made for pulling particular subtag-trees up to the tagset level (parents are then discarded).
#
# Consider the following example structure for a tagset:
#
# | top-level tags        | sub-tags ...
# ----------------------------------------------------------------------
#   narratological_tagset ─┌─ narrative_levels ─ etc.
#                          └─ character ─┌─ characterization ─ etc.
#                                        └─ character_reference ─ etc.
#   other_tag_tree ─ etc.
#
# Looking at the first few lines of the split_tag_hierarchy_into_tagsets function below, you can see that:
# * `toplevel_tags_to_consider = ["narratological_tagset"]` - meaning that the tag-trees under 'narratological_tagset'
#    will be turned into individual tagsets, named "narrative_levels" and so on, while 'other_tag_tree' will be
#    discarded
# * `subtags_to_turn_into_tagsets = { "character": ["characterization", "character_reference"] }` - meaning that
#    'character' and its sub-trees will be handled in a special way, with 'characterization' and 'character_reference'
#    being turned into tagsets while any parents up the chain (including 'character') will be discarded
#    (the immediate parent is specified in `subtags_to_turn_into_tagsets` to ensure that the correct tags are selected)
#
# `tags_to_ignore` can be used to manually specify sub-trees to discard. For example, adding 'narrative_levels' to this
# list would discard 'narrative_levels' and its children. Note that the parent of the sub-tree to discard must be one of
# the top-level tags. `tags_to_ignore` is also populated automatically based on `subtags_to_turn_into_tagsets`.
# Note: the ignore mechanism could be optimised so that the `get_all_parents` function does not return top-level tags,
# which causes the entries for top-level tags to be duplicated when `subtags_to_turn_into_tagsets` is used.

from catma_py.catma import TEIAnnotationReader, TEIAnnotationWriter, Tagset


def get_subtag_parent(tagset, k, v, expected_parent):
    parent_tag = [
        tag for tag in tagset.tags.values() if tag.parent == expected_parent and tag.name == k
    ][0]

    if isinstance(v, dict):
        return get_subtag_parent(tagset, list(v.keys())[0], list(v.values())[0], parent_tag)
    else:
        return parent_tag, v


def get_all_parents(tag_and_parents, tag):
    if tag.parent is not None:
        tag_and_parents.append(tag.parent)
        return get_all_parents(tag_and_parents, tag.parent)
    else:
        return tag_and_parents


def recursively_get_tags(tagset, parent_tag, iteration: int = 0):
    tags = [tag for tag in tagset.tags.values() if tag.parent == parent_tag]

    children = []
    for tag in tags:
        children.extend(recursively_get_tags(tagset, tag, iteration + 1))
    tags.extend(children)

    if iteration == 0:  # throw away parent where it is parent_tag
        for tag in tags:
            if tag.parent == parent_tag:
                tag.parent = None

    return tags


def split_tag_hierarchy_into_tagsets():
    toplevel_tags_to_consider = ["narratological_tagset"]
    tags_to_ignore = []
    subtags_to_turn_into_tagsets = {  # mapped to parents to make sure we have the right ones, parents are ignored
        "character": ["characterization", "character_reference"]
    }
    subtags_to_turn_into_tagsets_objs = []

    reader = TEIAnnotationReader(r"/path/to/input.xml", False)
    tagset = reader.tagsets[0]

    toplevel_tags = [
        tag for tag in tagset.tags.values() if tag.parent is None and tag.name in toplevel_tags_to_consider
    ]

    for tl_tag in toplevel_tags:
        tags_to_ignore.append(tl_tag)

        for k, v in subtags_to_turn_into_tagsets.items():
            expected_parent, tag_names = get_subtag_parent(tagset, k, v, tl_tag)
            tags_to_ignore.extend(get_all_parents([expected_parent], expected_parent))
            subtags_to_turn_into_tagsets_objs.extend(
                [tag for tag in tagset.tags.values() if tag.parent == expected_parent and tag.name in tag_names]
            )

        # all other tags under tl_tag
        subtags_to_turn_into_tagsets_objs.extend(
            [tag for tag in tagset.tags.values() if tag.parent == tl_tag and tag not in tags_to_ignore]
        )

    new_tagsets = []

    for subtag in subtags_to_turn_into_tagsets_objs:
        new_tagset = Tagset(
            subtag.name,
            recursively_get_tags(tagset, subtag)
        )
        new_tagsets.append(new_tagset)

    writer = TEIAnnotationWriter(0, "empty", new_tagsets, [])
    writer.write_to_tei(r"/path/to/output.xml", False)
