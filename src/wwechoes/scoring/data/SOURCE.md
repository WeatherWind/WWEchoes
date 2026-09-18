# 角色评分配置来源

角色词条权重（skill_weight / main_props / sub_props / score_max / grade）提取自 WutheringWavesUID 的 `utils/map/character/<角色>/calc.json`，该项目为 **GPL-3.0**，故本文件及其衍生（characters.json）同样受 GPL-3.0 约束，不得脱离 GPL 许可证分发。

```
repo=ChenXun-123/WutheringWavesUID
branch=master
commit=1d693a2df0f940824cb34e102cec1cf3b381e70f
pushed_at=2025-11-23T09:43:09Z
fetched=2026-09-18
```

更新方式：`python scripts/vendor_wwuid.py`（勿手改 characters.json）。
已知边界：快照晚于该日期上线的新角色未收录，评分时回落 `__default__` 通用权重。
