Name:           lh-pcb-thermal-sim
Version:        0.1.0
Release:        1%{?dist}
Summary:        lh-pcb-thermal - 2D Finite-Difference Successive Over-Relaxation PDE Solver
License:        Apache-2.0
URL:            https://github.com/Logihertz-Systems-OPC-Pvt-Ltd/lh-pcb-thermal-sim
Source0:        %{name}-%{version}-src.tar.gz
Packager:       Sameer Tawade <ops@logihertz.com>
BuildArch:      noarch

%description
Multi-layer PCB 2D steady-state Successive Over-Relaxation (SOR) Finite-Difference thermal simulator with anisotropic Cu/FR-4 conductivity homogenization, thermal via resistance, and IPC-2152 trace heating math.

%prep
%autosetup -n %{name}-0.1.0

%build
# Industrial clean-room build with zero external runtime dependencies

%install
rm -rf %{buildroot}
mkdir -p %{buildroot}%{_bindir}
mkdir -p %{buildroot}%{_docdir}/%{name}
mkdir -p %{buildroot}%{_mandir}/man1

if [ -f bin/lh-pcb-thermal ]; then
    install -m 0755 bin/lh-pcb-thermal %{buildroot}%{_bindir}/lh-pcb-thermal
elif [ -f lh-pcb-thermal ]; then
    install -m 0755 lh-pcb-thermal %{buildroot}%{_bindir}/lh-pcb-thermal
fi

install -m 0644 README.md %{buildroot}%{_docdir}/%{name}/README.md
install -m 0644 SPEC.md %{buildroot}%{_docdir}/%{name}/SPEC.md
install -m 0644 LICENSE %{buildroot}%{_docdir}/%{name}/LICENSE
install -m 0644 NOTICE %{buildroot}%{_docdir}/%{name}/NOTICE

%files
%doc %{_docdir}/%{name}/README.md
%doc %{_docdir}/%{name}/SPEC.md
%doc %{_docdir}/%{name}/NOTICE
%license %{_docdir}/%{name}/LICENSE

%changelog
* Mon Nov 16 2026 Sameer Tawade <ops@logihertz.com> - 0.1.0-1
- Initial production release for Logihertz Systems Ecosystem and STRUCT OS.
