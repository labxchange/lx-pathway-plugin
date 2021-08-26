LabXchange "Pathway" Plugin for Open edX
========================================

This is a django app plugin that implements "Pathways" as an Open edX learning
context. It exposes pathway functionality via a REST API and integrates with the
XBlock runtime and XBlock REST APIs.

A "Pathway" is a short collection of XBlocks that a student works through in a
linear sequence.

(How is this different from a Unit/Vertical? Pathways can have some extra
metadata such as notes associated with each child, and pathways exist as a
top-level learning context, like a course or a content library. XBlocks like
Unit/Vertical can't exist outside of a learning context.)


## Installation on Devstack

```
make studio-shell
cd /edx/src
git clone https://github.com/open-craft/lx-pathway-plugin.git
pip install -e /edx/src/lx-pathway-plugin
```

## Testing on Devstack

From the blockstore repo:

```
make testserver
```

From devstack:

```
make studio-shell
make -f /edx/src/lx-pathway-plugin/Makefile validate
```
