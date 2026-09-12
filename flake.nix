{
  description = "Parametron FreeCAD development environment";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = { self, nixpkgs }:
    let
      system = "x86_64-linux";
      pkgs = import nixpkgs { inherit system; };

      python = pkgs.python314.withPackages (ps: [
        ps.pytest
      ]);

      # Snapshot of this flake's source; used so the wrapper does not depend on cwd.
      parametronFreecadSrc = ./.;

      parametron-freecad = pkgs.writeShellApplication {
        name = "parametron-freecad";
        runtimeInputs = [
          pkgs.freecad
          python
        ];
        text = ''
          export PYTHONPATH="${parametronFreecadSrc}:''${PYTHONPATH:-}"
          exec ${python}/bin/python -m parametron_freecad.runtime.launcher "$@"
        '';
      };
    in
    {
      packages.${system} = {
        inherit parametron-freecad;
        default = parametron-freecad;
      };

      apps.${system}.default = {
        type = "app";
        program = "${parametron-freecad}/bin/parametron-freecad";
      };

      devShells.${system}.default = pkgs.mkShell {
        packages = [
          pkgs.freecad
          python
          parametron-freecad
        ];

        shellHook = ''
          echo "Parametron FreeCAD dev shell"
          echo "Python: $(python --version)"
          echo "Pytest: $(python -m pytest --version)"
          echo "FreeCAD: $(freecadcmd --version | head -n 1 || true)"
          echo "Wrapper: $(command -v parametron-freecad || true)"
        '';
      };
    };
}
