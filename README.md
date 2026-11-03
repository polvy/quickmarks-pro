[README.md](https://github.com/user-attachments/files/34313306/README.md)

# Quickmarks Pro

**Fast, named network locations for Houdini.** Press a hotkey, type a few letters, hit Enter, and you're back in the network, view and node selection you saved. Unlimited quickmarks, stored inside your `.hip`.

Houdini's built-in quickmarks are numbered slots with no names. Quickmarks Pro replaces them with a searchable popup, so jumping between `OUT\_debris`, `OUT\_smoke`, your LOPs, TOPs and ROPs takes about a second.

## Features

* **Unlimited, named quickmarks.** Call them `debris`, `smoke`, `usd`, whatever you like.
* **Type to jump.** Type a few letters, press **Enter**. Names are matched by prefix first, then anywhere in the name.
* **Tab to complete** the highlighted name. Arrow keys or a mouse click work too.
* **One-step saving.** Type a name that doesn't exist yet and press **Enter**: the current location is saved straight away.
* **Remembers more than the path.** Each quickmark stores the network, the exact view (pan and zoom), and optionally the selected nodes.
* **Most recently used first.** With an empty field, your latest quickmarks are at the top.
* **Missing nodes are greyed out** and marked `(missing)`; one button removes them all.
* **Stored in the `.hip` itself**, so quickmarks travel with the scene and with every saved version.
* **Works with any network editor** (SOPs, LOPs, TOPs, ROPs, DOPs...): it acts on the editor under your cursor.

## Install

1. In Houdini, right-click a shelf and choose **New Tool...**
2. Give it a name (for example `Quickmarks Pro`) and click **Accept**.
3. In the **Script** tab, set the language to **Python** and paste the whole contents of `quickmarks\_pro\_shelf.py`.
4. In the **Options** tab, set a **Hotkey** (for example `alt+K`). If the key is already used, Houdini warns you about the conflict.

## Keys

|Key|Action|
|-|-|
|*type*|Filter quickmarks by name|
|`Up` / `Down`|Move the selection|
|`Tab`|Complete the highlighted name|
|`Enter`|Jump to the highlighted quickmark. If nothing matches, save the current location under the typed name|
|`Ctrl+S`|Save the current location. With a name typed, saves immediately (also when it only partly matches another quickmark); with an empty field, asks for a name|
|`Ctrl+D`|Delete the highlighted quickmark|
|`Esc`|Cancel|

Updating a quickmark: save again with the same name (the match is not case-sensitive) and it moves to the current location.

## Where the data lives

Quickmarks are stored as text in the user data of the scene's root node, under the key `quickmarksPro`. Houdini writes it into the `.hip` when you save the scene, so **save the `.hip` to keep new quickmarks**. Saving a quickmark does not add an undo step, but it does mark the scene as modified.

You can inspect or reset it from Houdini's Python shell:

```python
hou.node("/").userData("quickmarksPro")          # see what's stored
hou.node("/").destroyUserData("quickmarksPro")   # remove all quickmarks in this scene
```

Quickmarks saved with earlier versions of this tool (user data keys `advancedQuickmarks` and `networkShortcuts`, or a `networkShortcuts.json` next to the `.hip`) are imported automatically the first time a scene has none.

## Notes

* Selection is remembered only for nodes that sit directly inside the network you were in when you saved.
* Merging another `.hip` into your scene doesn't bring its quickmarks along; only the current scene's apply.
* The popup uses PySide6 and falls back to PySide2, so it should run on current Houdini builds.

## Compatibility

Tested on: *h22.0.466*

## 

