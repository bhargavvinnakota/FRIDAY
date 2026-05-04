import sys
import os
sys.path.insert(0, os.path.expanduser("~/AI"))
from friday.skills.registry import get_registry

reg = get_registry()
skill = reg.get("omni_learner")
if skill:
    print("OmniLearner found!")
    res = skill.invoke("train_across_models", topic="How to build self-improving AI agents.")
    print(res)
else:
    print("OmniLearner not found!")
