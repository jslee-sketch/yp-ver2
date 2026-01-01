# scripts/verify_policy_loader.py
from __future__ import annotations

from app.policy.params.loader import load_policy_yaml


def main():
    bundle = load_policy_yaml()
    print("=== POLICY LOADED OK ===")
    print(bundle)
    print("========================")


if __name__ == "__main__":
    main()