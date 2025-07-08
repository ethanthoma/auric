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
          pkgs = inputs.nixpkgs.legacyPackages.${system}.extend (
            inputs.nixpkgs.lib.composeManyExtensions [
              inputs.devshell.overlays.default
              self.overlays.default
            ]
          );

          python =
            let
              version = pkgs.lib.removeSuffix "\n" (builtins.readFile ./.python-version);
              major = builtins.substring 0 1 version;
              minor = builtins.substring 2 2 version;
              packageName = "python${major}${minor}";
            in
            pkgs.${packageName} or pkgs.python312;
        in
        {
          _module.args.pkgs = pkgs;

          devshells.default = {
            packages = [
              pkgs.ruff
              pkgs.ty
            ];

            env =
              [
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
              { package = pkgs.gemini-cli; }
              {
                name = "demo";
                command = "uv run --with . --no-project --refresh-package auric -- python example/demo.py";
                category = "example(s)";
              }
            ];
          };
        };
    }
    // {
      overlays.default = final: prev: {
        ruff = prev.ruff.overrideAttrs (oldAttrs: {
          nativeBuildInputs = (oldAttrs.nativeBuildInputs or [ ]) ++ [ final.makeWrapper ];

          postFixup =
            (oldAttrs.postFixup or "")
            + ''
              wrapProgram $out/bin/ruff \
                --suffix PATH : ${final.lib.makeBinPath [ prev.ruff ]}
            '';
        });

        ty = prev.ty.overrideAttrs (
          finalAttrs: prevAttrs: {
            version = "0.0.1-alpha.13";

            src = prevAttrs.src.override {
              hash = "sha256-w+eYclC9X0T1f/oj8MY4KG72lpAVGpMjjchER167sp0=";
            };

            cargoDeps = prev.pkgs.rustPlatform.importCargoLock {
              lockFile = "${finalAttrs.src}/ruff/Cargo.lock";
              outputHashes = {
                "lsp-types-0.95.1" = "sha256-8Oh299exWXVi6A39pALOISNfp8XBya8z+KT/Z7suRxQ=";
                "salsa-0.23.0" = "sha256-jVL/Y548jv8RJ1rgBdJcsGtwIsH2aLxBbgO4FZl78wc=";
              };
            };
          }
        );
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
