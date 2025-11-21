import sys, importlib
sys.path.insert(0, r"C:\Users\user\Desktop\yp-ver2")
R = importlib.import_module("app.config.project_rules")
print("time overridden:", getattr(R, "is_test_time_overridden", lambda:None)())
print("now:", R.now_utc().isoformat())
