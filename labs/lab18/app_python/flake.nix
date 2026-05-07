{
  description = "DevOps Info Service - Reproducible Build with Nix Flakes";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-24.11";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        app = import ./default.nix { inherit pkgs; };
      in
      {
        packages = {
          default = app;
          dockerImage = import ./docker.nix { inherit pkgs; };
        };

        apps.default = {
          type = "app";
          program = "${app}/bin/devops-info-service";
        };

        devShells.default = pkgs.mkShell {
          buildInputs = with pkgs; [
            python3
            python3Packages.fastapi
            python3Packages.uvicorn
            python3Packages.prometheus-client
            python3Packages.starlette
          ];

          shellHook = ''
            echo "DevOps Info Service dev shell"
            echo "Python: $(python --version)"
            echo "Run: python app.py"
          '';
        };
      });
}
