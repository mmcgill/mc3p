
# Plugins

## Installation and Activation

To install a plugin, simply copy it to the `plugins` subdirectory of the
MC3P directory. Installing a plugin does not *activate* it, however.
To activate a plugin, add its file name to the `mc3p.conf` file
in the MC3P directory. `mc3p.conf` is simply a list of active
plugins, in order of decreasing *precedence*.

## Plugin Precedence

When multiple active plugins have message handlers for the
same message type, *plugin precedence* determines the order
in which the message handlers are invoked. MC3P invokes
message handlers one-at-a-time, in order of decreasing
precedence, until a handler returns `False`.
Once a message handler returns `False` for a given message, no other handler
is invoked for that message.

## Anatomy of a Plugin

An MC3P plugin is a Python module containing one or more
*message handler*. Each message handler
is associated with a single Minecraft message type.

MC3P recognizes a message handler, and matches it to a type,
based on its name.
When MC3P loads a plugin module, it assumes that each
function with a name of the form
`handle_msgXX` is the message handler for Minecraft message
type XX.

Each message handler should have the signature:

    handle_msgXX(msg, dst)

* `msg` is a dictionary-like object that maps field names to values.
* `dst` is either the string "client" or the string "server", and
  indicates the message's destination.

Each message handler should return a boolean value that
indicates whether MC3P should forward the message:
if `True` is returned, the message is forward; if `False`,
it is not.

The message handler may modify the values of `msg` as desired,
but may not add or remove mappings. MC3P will send the modified
version of the packet along to the client.

