This is an unfinished playbook that allowed me to bootstrap and configure my computer.

It was ment to configure a computer of mine from other computer/tablet make disk partitions,
downloading `/etc/` from an etckeetper repo which also has a list of installed packages,
install all those packages and reboot the computer.

At the end was a nightmare of `when` clauses to know where does pacman has to run or use a `--root`.

There is also a problem is that arch repositories and archiso could not have the same kernel so a zfs module could fail to install.

All of this at the end in a cyclic dependency/race condition between ZFS unmount and mark as bootstrapped and handlers could collide.

In the end formating a PC is something that I do when you buy a new device and has now enought devices so I prefer to do this playbook maintenance.

It was a really fun to learn some complex playbooks (which are not as complex as Red Hat's Openshift).

# Deprecated