{ pkgs ? import <nixpkgs> {} }:

pkgs.python3Packages.buildPythonApplication {
  pname = "devops-info-service";
  version = "1.0.0";
  src = pkgs.lib.cleanSourceWith {
    src = ./.;
    filter = path: type:
      let baseName = baseNameOf (toString path);
      in !(
        baseName == "result"
        || baseName == "Dockerfile"
        || pkgs.lib.hasPrefix "nix-image-" baseName
        || pkgs.lib.hasSuffix ".tar.gz" baseName
        || baseName == "__pycache__"
        || baseName == ".pytest_cache"
        || baseName == "venv"
      );
  };

  format = "other";

  propagatedBuildInputs = with pkgs.python3Packages; [
    fastapi
    uvicorn
    prometheus-client
    starlette
  ];

  nativeBuildInputs = [ pkgs.makeWrapper ];

  installPhase = ''
    mkdir -p $out/bin $out/lib
    cp app.py $out/lib/app.py

    cat > $out/bin/.devops-info-service-launcher <<'EOF'
    #!${pkgs.python3}/bin/python
    import os, uvicorn
    uvicorn.run(
        "app:app",
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "5000")),
        log_level="info",
    )
    EOF
    chmod +x $out/bin/.devops-info-service-launcher

    makeWrapper $out/bin/.devops-info-service-launcher $out/bin/devops-info-service \
      --prefix PYTHONPATH : "$out/lib:$PYTHONPATH" \
      --set-default PORT "5000" \
      --set-default HOST "0.0.0.0"
  '';

  doCheck = false;
}
