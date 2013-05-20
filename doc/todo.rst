=====
To do
=====

 * hook that gets notified about all installations
 * binary deltas?
 * dbus interface etc. as backend for UI
  * method may not be feasible because caller may want to go away
  * but where do we send a completion/failure signal back to?
 * drop privileges to software user when unpacking; retain root for hook execution
 * arrangement to reprocess hooks on whole-image-update
 * support for installing some apps to phone memory and some to an SD card
 * some way to manage shared data files
 * localised metadata
 * source packages, at least for free software
