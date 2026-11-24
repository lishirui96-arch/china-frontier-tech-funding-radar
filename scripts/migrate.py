from funding_radar.migrations import migrate

if __name__ == "__main__":
    print(f"schema_version={migrate()}")

