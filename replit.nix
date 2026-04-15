{ pkgs }: {
  deps = [
    pkgs.python311
    pkgs.python311Packages.pip
    pkgs.sqlite
    pkgs.stdenv.cc.cc.lib
  ];
}
