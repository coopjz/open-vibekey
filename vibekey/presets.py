"""WorkBuddy profiles recovered from Studio, plus native CLI interaction profiles."""
import copy

from .config import CONTROLS


def presets():
    result = {}
    for pid, name, knob, description in (
        ("workbuddy-default", "默认预设", "SHIFT+ALT+W", "唤起 WorkBuddy · 滚动内容"),
        ("workbuddy-dispatch", "快速派活", "CTRL+N", "新建会话 · 连续派发任务"),
        ("workbuddy-multitask", "多任务模式", "SHIFT+ALT+W", "唤起 WorkBuddy · 切换任务"),
    ):
        bindings = {
            control: {"single": {"type": "shortcut", "keys": keys, "label": label}}
            for control, keys, label in (
                ("top", "CTRL+D", "语音输入"), ("middle", "ENTER", "发送消息"),
                ("bottom", "ESC", "停止生成"),
                ("knob", knob, "新建会话" if knob == "CTRL+N" else "唤起 WorkBuddy"),
                ("ccw", "CTRL+LEFTBRACE", "上一个任务"),
                ("cw", "CTRL+RIGHTBRACE", "下一个任务"),
            )
        }
        if pid == "workbuddy-default":
            bindings["ccw"] = {"single": {"type": "scroll", "direction": "up"}}
            bindings["cw"] = {"single": {"type": "scroll", "direction": "down"}}
        layers = [{"name": "主层", "bindings": bindings}]
        layers.extend({"name": "Layer %d" % i, "bindings": {
            c: {"single": {"type": "inherit"}} for c in CONTROLS}} for i in range(1, 4))
        result[pid] = {"description": description, "profile": {"name": name, "layers": layers}}
    for pid, name, knob, label, description in (
        ("codex-cli", "Codex CLI", "CTRL+R", "搜索提示历史", "语音输入 · 发送确认 · 历史导航"),
        ("claude-code", "Claude Code", "CTRL+O", "展开对话详情", "语音输入 · 发送确认 · 对话详情"),
    ):
        layers = copy.deepcopy(result["workbuddy-default"]["profile"]["layers"])
        layers[0]["bindings"] = {
            "top": {"single": {"type": "shortcut", "keys": "RIGHTALT", "mode": "hold", "label": "语音输入"}},
            **{control: {"single": {"type": "shortcut", "keys": keys, "label": title}}
               for control, keys, title in (
                   ("middle", "ENTER", "发送 / 确认"), ("bottom", "ESC", "中断 / 取消"),
                   ("knob", knob, label), ("cw", "DOWN", "下一条历史"), ("ccw", "UP", "上一条历史"))},
        }
        result[pid] = {"description": description, "profile": {"name": name, "layers": layers}}
    return copy.deepcopy(result)
