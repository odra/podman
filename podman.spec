# For automatic rebuilds in COPR

# The following tag is to get correct syntax highlighting for this file in vim text editor
# vim: syntax=spec

%global with_debug 1

# _user_tmpfiles.d currently undefined on rhel
%if 0%{?fedora} <= 35 || 0%{?rhel}
%global _user_tmpfilesdir %{_datadir}/user-tmpfiles.d
%endif

%if 0%{?with_debug}
%global _find_debuginfo_dwz_opts %{nil}
%global _dwz_low_mem_die_limit 0
%else
%global debug_package %{nil}
%endif

%if ! 0%{?gobuild:1}
%define gobuild(o:) go build -buildmode pie -compiler gc -tags="rpm_crashtraceback ${BUILDTAGS:-}" -ldflags "${LDFLAGS:-} -B 0x$(head -c20 /dev/urandom|od -An -tx1|tr -d ' \\n') -extldflags '-Wl,-z,relro -Wl,-z,now -specs=/usr/lib/rpm/redhat/redhat-hardened-ld '" -a -v -x %{?**};
%endif

# git_dir_name returns repository name derived from remote Git repository URL
Name:       {{{ git_dir_name }}}

Epoch: 101

# git_dir_version returns version based on commit and tag history of the Git project
Version:    {{{ git_dir_version }}}

# This can be useful later for adding downstream patches
Release:    1%{?dist}

# Basic description of the package
Summary: Manage Pods, Containers and Container Images

# License. We assume GPLv2+ here.
License:   ASL 2.0

# Home page of the project. Can also point to the public Git repository page.
URL:        https://github.com/containers/podman

# Detailed information about the source Git repository and the source commit
# for the created rpm package
VCS:        {{{ git_dir_vcs }}}

# git_dir_pack macro places the repository content (the source files) into a tarball
# and returns its filename. The tarball will be used to build the rpm.
Source:     {{{ git_dir_pack }}}

%if 0%{?fedora} && ! 0%{?rhel}
BuildRequires: btrfs-progs-devel
%endif
BuildRequires: gcc
BuildRequires: golang >= 1.16.6
BuildRequires: glib2-devel
BuildRequires: glibc-devel
BuildRequires: glibc-static
BuildRequires: git-core
BuildRequires: go-md2man
%if 0%{?fedora} || 0%{?rhel} >= 9
BuildRequires: go-rpm-macros
%endif
%if 0%{?rhel} <= 8
BuildRequires: pkgconfig(devmapper)
BuildRequires: python3
%endif
BuildRequires: gpgme-devel
BuildRequires: libassuan-devel
BuildRequires: libgpg-error-devel
BuildRequires: libseccomp-devel
BuildRequires: libselinux-devel
BuildRequires: shadow-utils-subid-devel
BuildRequires: pkgconfig
BuildRequires: make
BuildRequires: ostree-devel
%{?systemd_requires}
BuildRequires: systemd
BuildRequires: systemd-devel
Requires: conmon >= 2:2.0.30-2
Requires: containers-common-extra >= 4:1-78
Requires: iptables
Requires: nftables
Recommends: catatonit
Suggests: qemu-user-static

# More detailed description of the package
%description
%{name} (Pod Manager) is a fully featured container engine that is a simple
daemonless tool.  %{name} provides a Docker-CLI comparable command line that
eases the transition from other container engines and allows the management of
pods, containers and images.  Simply put: alias docker=%{name}.
Most %{name} commands can be run as a regular user, without requiring
additional privileges.

%{name} uses Buildah(1) internally to create container images.
Both tools share image (not container) storage, hence each can use or
manipulate images (but not containers) created by the other.

%package docker
Summary: Emulate Docker CLI using %{name}
BuildArch: noarch
Requires: %{name} = %{epoch}:%{version}-%{release}
Conflicts: docker
Conflicts: docker-latest
Conflicts: docker-ce
Conflicts: docker-ee
Conflicts: moby-engine

%description docker
This package installs a script named docker that emulates the Docker CLI by
executes %{name} commands, it also creates links between all Docker CLI man
pages and %{name}.

%package tests
Summary: Tests for %{name}
Requires: %{name} = %{epoch}:%{version}-%{release}
Requires: bats
Requires: jq
Requires: skopeo
Requires: nmap-ncat
Requires: httpd-tools
Requires: openssl
Requires: socat
Requires: buildah
Requires: gnupg

%description tests
%{summary}

This package contains system tests for %{name}

%package remote
Summary: (Experimental) Remote client for managing %{name} containers

%description remote
Remote client for managing %{name} containers.

%{name}-remote uses the libpod REST API to connect to a %{name} client to
manage pods, containers and container images. %{name}-remote supports ssh
connections as well.

%package quadlet
Summary: Easily create systemd services using %{name}
Requires: %{name} = %{epoch}:%{version}-%{release}
Conflicts: quadlet

%description quadlet
This package installs a systemd generator for *.container files in
/etc/containers/systemd. Such files are automatically converted into
systemd service units, allowing easily written and maintained
podman-based system services.

# The following four sections already describe the rpm build process itself.
# prep will extract the tarball defined as Source above and descend into it.
%prep
{{{ git_dir_setup_macro }}}

# This will invoke `make` command in the directory with the extracted sources.
%build
%set_build_flags
%global gomodulesmode GO111MODULE=on
export CGO_CFLAGS=$CFLAGS
# These extra flags present in $CFLAGS have been skipped for now as they break the build
CGO_CFLAGS=$(echo $CGO_CFLAGS | sed 's/-flto=auto//g')
CGO_CFLAGS=$(echo $CGO_CFLAGS | sed 's/-Wp,D_GLIBCXX_ASSERTIONS//g')
CGO_CFLAGS=$(echo $CGO_CFLAGS | sed 's/-specs=\/usr\/lib\/rpm\/redhat\/redhat-annobin-cc1//g')

%ifarch x86_64
export CGO_CFLAGS+=" -m64 -mtune=generic -fcf-protection=full"
%endif

%if 0%{?rhel}
rm -rf vendor/github.com/containers/storage/drivers/register/register_btrfs.go
%endif

# build date. FIXME: Makefile uses '/v2/libpod', that doesn't work here?
LDFLAGS="-X ./libpod/define.buildInfo=$(date +%s)"

# build rootlessport first
%gobuild -o bin/rootlessport ./cmd/rootlessport

# set base buildtags common to both %%{name} and %%{name}-remote
export BASEBUILDTAGS="seccomp exclude_graphdriver_devicemapper $(hack/selinux_tag.sh) $(hack/systemd_tag.sh) $(hack/libsubid_tag.sh)"

# build %%{name}
export BUILDTAGS="$BASEBUILDTAGS $(hack/btrfs_installed_tag.sh) $(hack/btrfs_tag.sh)"
%gobuild -o bin/%{name} ./cmd/%{name}

# build %%{name}-remote
export BUILDTAGS="$BASEBUILDTAGS exclude_graphdriver_btrfs btrfs_noversion remote"
%gobuild -o bin/%{name}-remote ./cmd/%{name}

# build quadlet
export BUILDTAGS="$BASEBUILDTAGS $(hack/btrfs_installed_tag.sh) $(hack/btrfs_tag.sh)"
%gobuild -o bin/quadlet ./cmd/quadlet

make docs docker-docs

# This will copy the files generated by the `make` command above into
# the installable rpm package.
%install
PODMAN_VERSION=%{version} %{__make} DESTDIR=%{buildroot} PREFIX=%{_prefix} ETCDIR=%{buildroot}%{_sysconfdir} \
        install.bin \
        install.man \
        install.systemd \
        install.completions \
        install.docker \
        install.docker-docs \
        install.remote \
%if 0%{?fedora} >= 36
        install.modules-load
%endif

install -d -p %{buildroot}/%{_datadir}/%{name}/test/system
cp -pav test/system %{buildroot}/%{_datadir}/%{name}/test/

# do not include docker and podman-remote man pages in main package
for file in `find %{buildroot}%{_mandir}/man[15] -type f | sed "s,%{buildroot},," | grep -v -e remote -e docker`; do
    echo "$file*" >> podman.file-list
done

%post
if [ $1 -eq 1 ]; then
    %{_bindir}/systemctl enable --now %{name}-restart.service
fi

%preun
%systemd_preun %{name}-restart.service

%postun
%systemd_postun %{name}-restart.service

# This lists all the files that are included in the rpm package and that
# are going to be installed into target system where the rpm is installed.
%files -f %{name}.file-list
%license LICENSE
%doc README.md CONTRIBUTING.md install.md transfer.md
%{_bindir}/%{name}
%dir %{_libexecdir}/%{name}
%{_libexecdir}/%{name}/rootlessport
%{_datadir}/bash-completion/completions/%{name}
# By "owning" the site-functions dir, we don't need to Require zsh
%dir %{_datadir}/zsh/site-functions
%{_datadir}/zsh/site-functions/_%{name}
%dir %{_datadir}/fish/vendor_completions.d
%{_datadir}/fish/vendor_completions.d/%{name}.fish
%{_unitdir}/%{name}-auto-update.service
%{_unitdir}/%{name}-auto-update.timer
%{_unitdir}/%{name}.service
%{_unitdir}/%{name}.socket
%{_unitdir}/%{name}-restart.service
%{_unitdir}/%{name}-kube@.service
%{_unitdir}/%{name}-clean-transient.service
%{_userunitdir}/%{name}-auto-update.service
%{_userunitdir}/%{name}-auto-update.timer
%{_userunitdir}/%{name}.service
%{_userunitdir}/%{name}.socket
%{_userunitdir}/%{name}-restart.service
%{_userunitdir}/%{name}-kube@.service
%{_tmpfilesdir}/%{name}.conf
%{_user_tmpfilesdir}/%{name}-docker.conf
%if 0%{?fedora} >= 36
%{_modulesloaddir}/%{name}-iptables.conf
%endif

%files docker
%{_bindir}/docker
%{_mandir}/man1/docker*.1*
%{_mandir}/man5/docker*.5*
%{_usr}/lib/tmpfiles.d/%{name}-docker.conf

%files quadlet
%license LICENSE
%{_libexecdir}/%{name}/quadlet
%_prefix/lib/systemd/system-generators/podman-system-generator
%_prefix/lib/systemd/user-generators/podman-user-generator

%files remote
%license LICENSE
%{_bindir}/%{name}-remote
%{_mandir}/man1/%{name}-remote*.*
%{_datadir}/bash-completion/completions/%{name}-remote
%dir %{_datadir}/fish/vendor_completions.d
%{_datadir}/fish/vendor_completions.d/%{name}-remote.fish
%dir %{_datadir}/zsh/site-functions
%{_datadir}/zsh/site-functions/_%{name}-remote

%files tests
%license LICENSE
%{_datadir}/%{name}/test

# Finally, changes from the latest release of your application are generated from
# your project's Git history. It will be empty until you make first annotated Git tag.
%changelog
{{{ git_dir_changelog }}}
