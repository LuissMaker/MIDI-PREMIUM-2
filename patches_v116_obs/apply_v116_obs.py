from pathlib import Path
import sys

root=Path(sys.argv[1])
panel_src=Path(sys.argv[2]).read_text(encoding="utf-8")
(root/"app_source/app/widgets/obs_panel.py").write_text(panel_src, encoding="utf-8")

p=root/"app_source/app/ui/main_window.py"
s=p.read_text(encoding="utf-8")

# Move OBS panel above ActionEditor and prevent ActionEditor from consuming all height.
old='''        layout.addWidget(QLabel("Tipo de acción"))
        layout.addWidget(self.action_editor, 1)
        layout.addWidget(self.obs_panel)
        layout.addLayout(buttons)
'''
new='''        layout.addWidget(QLabel("Tipo de acción"))
        layout.addWidget(self.obs_panel)
        layout.addWidget(self.action_editor, 1)
        layout.addLayout(buttons)
'''
if old not in s:
    raise RuntimeError("editor layout block not found")
s=s.replace(old,new,1)

old='''    def _sync_main_obs_visibility(self, action_type: str) -> None:
        self.obs_panel.setVisible(str(action_type).startswith("obs_"))
'''
new='''    def _sync_main_obs_visibility(self, action_type: str) -> None:
        is_obs = str(action_type).startswith("obs_")
        self.obs_panel.setVisible(is_obs)
        if is_obs:
            self.action_editor.setMaximumHeight(245)
            self.action_editor.setMinimumHeight(120)
        else:
            self.action_editor.setMaximumHeight(16777215)
            self.action_editor.setMinimumHeight(0)
'''
if old not in s:
    raise RuntimeError("OBS visibility block not found")
s=s.replace(old,new,1)

s=s.replace('APP_VERSION = "1.1.15 Stable"', 'APP_VERSION = "1.1.16 Stable"')
s=s.replace('APP_VERSION = "1.1.14 Stable"', 'APP_VERSION = "1.1.16 Stable"')
p.write_text(s,encoding="utf-8")

p=root/"app_source/app/core/updater.py"
u=p.read_text(encoding="utf-8")
u=u.replace('APP_VERSION = "1.1.15 Stable"', 'APP_VERSION = "1.1.16 Stable"')
u=u.replace('APP_VERSION = "1.1.14 Stable"', 'APP_VERSION = "1.1.16 Stable"')
p.write_text(u,encoding="utf-8")
(root/"app_source/app/version.py").write_text('__version__ = "1.1.16 Stable"\n',encoding="utf-8")

print("v1.1.16 fixed OBS layout applied")
