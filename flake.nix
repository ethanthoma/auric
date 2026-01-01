{
  description = "A very basic flake";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs?ref=nixos-unstable";
    flake-parts.url = "github:hercules-ci/flake-parts";
    devshell.url = "github:numtide/devshell";
    pyproject-nix = {
      url = "github:nix-community/pyproject.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    uv2nix = {
      url = "github:adisbladis/uv2nix";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    pyproject-build-systems = {
      url = "github:pyproject-nix/build-system-pkgs";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.uv2nix.follows = "uv2nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs =
    inputs@{ self, ... }:

    inputs.flake-parts.lib.mkFlake { inherit inputs; } {
      imports = [ inputs.devshell.flakeModule ];

      systems = [
        "aarch64-darwin"
        "aarch64-linux"
        "i686-linux"
        "x86_64-darwin"
        "x86_64-linux"
      ];

      perSystem =
        { system, ... }:
        let
          pkgs = import inputs.nixpkgs {
            system = "x86_64-linux";
            config.allowUnfree = true;
            overlays = [ inputs.devshell.overlays.default ];
          };

          python =
            let
              version = pkgs.lib.removeSuffix "\n" (builtins.readFile ./.python-version);
              major = builtins.substring 0 1 version;
              minor = builtins.substring 2 2 version;
              packageName = "python${major}${minor}";
            in
            pkgs.${packageName} or pkgs.python313;
        in
        {
          _module.args.pkgs = pkgs;

          devshells.default = {
            packages = [
              pkgs.ruff
              pkgs.pyrefly
              pkgs.taplo
            ];

            env = [
              {
                name = "UV_PYTHON_DOWNLOADS";
                value = "never";
              }
              {
                name = "UV_PYTHON";
                value = python.interpreter;
              }
              {
                name = "PYTHONPATH";
                unset = true;
              }
              {
                name = "UV_NO_SYNC";
                value = "1";
              }
              {
                name = "REPO_ROOT";
                eval = "$(git rev-parse --show-toplevel)";
              }
            ]
            ++ inputs.nixpkgs.lib.lists.optional pkgs.stdenv.isLinux {
              name = "LD_LIBRARY_PATH";
              value = inputs.nixpkgs.lib.makeLibraryPath pkgs.pythonManylinuxPackages.manylinux1;
            };

            commands = [
              { package = pkgs.uv; }
              { package = pkgs.gcc; }
            ];
          };
        };
    };

  nixConfig = {
    extra-substituters = [
      "https://nix-community.cachix.org"
    ];
    extra-trusted-public-keys = [
      "nix-community.cachix.org-1:mB9FSh9qf2dCimDSUo8Zy7bkq5CX+/rkCWyvRCYg3Fs="
    ];
  };
}
