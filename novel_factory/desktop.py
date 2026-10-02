from __future__ import annotations

import json
import os
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Any, Callable

from .config import Settings
from .database import Database
from .services import NovelFactory
from .llm import CompatibleChatProvider
from .orchestrator import EpisodeOrchestrator


COLORS = {
    "bg": "#f4f5f9", "surface": "#ffffff", "sidebar": "#202334", "sidebar_hover": "#303449",
    "primary": "#6c55d9", "primary_dark": "#5741c1", "text": "#20253a", "muted": "#737b91",
    "line": "#e1e4ed", "success": "#24936e", "warning": "#d68d2c", "danger": "#d55353",
}


class NovelFactoryApp(tk.Tk):
    def __init__(self, factory: NovelFactory | None = None):
        super().__init__()
        if factory is None:
            settings = Settings.from_env()
            settings.ensure_directories()
            factory = NovelFactory(Database(settings.database_path), settings.upload_dir)
        self.factory = factory
        settings = Settings.from_env()
        self.ai_endpoint = settings.llm_endpoint
        self.ai_model = settings.llm_model
        self.ai_key = os.getenv("NOVEL_FACTORY_API_KEY", "")
        self.selected_novel_id: str | None = None
        self._jobs: queue.Queue[tuple[Callable[[], Any], Callable[[Any], None]]] = queue.Queue()
        self.title("AI Novel Factory")
        self.geometry("1280x800")
        self.minsize(1000, 650)
        self.configure(bg=COLORS["bg"])
        self._setup_styles()
        self._build_layout()
        self.after(100, self._poll_jobs)
        self.show_dashboard()

    def _setup_styles(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Treeview", background=COLORS["surface"], fieldbackground=COLORS["surface"],
                        foreground=COLORS["text"], rowheight=34, borderwidth=0, font=("Malgun Gothic", 10))
        style.configure("Treeview.Heading", background="#eceef5", foreground=COLORS["muted"],
                        borderwidth=0, font=("Malgun Gothic", 9, "bold"))
        style.map("Treeview", background=[("selected", "#e9e5fb")], foreground=[("selected", COLORS["primary_dark"])])
        style.configure("TCombobox", padding=7)

    def _build_layout(self) -> None:
        self.sidebar = tk.Frame(self, bg=COLORS["sidebar"], width=225)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        brand = tk.Frame(self.sidebar, bg=COLORS["sidebar"])
        brand.pack(fill="x", padx=20, pady=(26, 32))
        tk.Label(brand, text="✦", bg=COLORS["primary"], fg="white", font=("Arial", 17, "bold"),
                 width=2, height=1).pack(side="left")
        label = tk.Frame(brand, bg=COLORS["sidebar"])
        label.pack(side="left", padx=10)
        tk.Label(label, text="Novel Factory", bg=COLORS["sidebar"], fg="white",
                 font=("Malgun Gothic", 13, "bold")).pack(anchor="w")
        tk.Label(label, text="DESKTOP STUDIO", bg=COLORS["sidebar"], fg="#8f95ad",
                 font=("Arial", 7, "bold")).pack(anchor="w")

        self.nav_buttons: list[tk.Button] = []
        navigation = [
            ("▦  대시보드", self.show_dashboard), ("▤  작품 관리", self.show_novels),
            ("◫  참고소설 분석", self.show_references), ("♙  캐릭터·기억", self.show_memory),
            ("✎  회차 제작", self.show_episodes), ("✓  품질 검사", self.show_quality),
            ("↥  EPUB·출판", self.show_publishing),
        ]
        for text, command in navigation:
            button = tk.Button(self.sidebar, text=text, command=lambda c=command, b=None: c(), anchor="w",
                               relief="flat", borderwidth=0, bg=COLORS["sidebar"], fg="#c3c7d6",
                               activebackground=COLORS["sidebar_hover"], activeforeground="white",
                               font=("Malgun Gothic", 10), padx=22, pady=11, cursor="hand2")
            button.pack(fill="x", padx=10, pady=2)
            self.nav_buttons.append(button)
        tk.Label(self.sidebar, text="데이터는 PC에만 저장됩니다", bg=COLORS["sidebar"], fg="#777e96",
                 font=("Malgun Gothic", 8)).pack(side="bottom", pady=20)

        self.main = tk.Frame(self, bg=COLORS["bg"])
        self.main.pack(side="left", fill="both", expand=True)
        self.header = tk.Frame(self.main, bg=COLORS["surface"], height=76, highlightbackground=COLORS["line"], highlightthickness=1)
        self.header.pack(fill="x")
        self.header.pack_propagate(False)
        self.header_title = tk.Label(self.header, text="", bg=COLORS["surface"], fg=COLORS["text"],
                                     font=("Malgun Gothic", 18, "bold"))
        self.header_title.pack(side="left", padx=30)
        self.novel_picker = ttk.Combobox(self.header, state="readonly", width=28)
        self.novel_picker.pack(side="right", padx=30)
        self.novel_picker.bind("<<ComboboxSelected>>", self._select_novel)
        self.content = tk.Frame(self.main, bg=COLORS["bg"])
        self.content.pack(fill="both", expand=True, padx=28, pady=24)

    def _clear(self, title: str) -> None:
        self.header_title.config(text=title)
        for child in self.content.winfo_children():
            child.destroy()
        self._refresh_novel_picker()

    def _refresh_novel_picker(self) -> None:
        novels = self.factory.list_novels()
        self._novel_options = {f"{item['title']}  ·  {item['genre']}": item["id"] for item in novels}
        self.novel_picker["values"] = list(self._novel_options)
        if self.selected_novel_id:
            for label, novel_id in self._novel_options.items():
                if novel_id == self.selected_novel_id:
                    self.novel_picker.set(label)
                    break
        elif novels:
            self.selected_novel_id = novels[0]["id"]
            self.novel_picker.current(0)

    def _select_novel(self, _event=None) -> None:
        self.selected_novel_id = self._novel_options.get(self.novel_picker.get())

    def _card(self, parent: tk.Widget, title: str, value: str, subtitle: str, column: int) -> None:
        card = tk.Frame(parent, bg=COLORS["surface"], highlightbackground=COLORS["line"], highlightthickness=1)
        card.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 7, 7 if column < 3 else 0))
        tk.Label(card, text=title, bg=COLORS["surface"], fg=COLORS["muted"], font=("Malgun Gothic", 9)).pack(anchor="w", padx=18, pady=(16, 2))
        tk.Label(card, text=value, bg=COLORS["surface"], fg=COLORS["text"], font=("Malgun Gothic", 22, "bold")).pack(anchor="w", padx=18)
        tk.Label(card, text=subtitle, bg=COLORS["surface"], fg=COLORS["success"], font=("Malgun Gothic", 8)).pack(anchor="w", padx=18, pady=(1, 15))

    def show_dashboard(self) -> None:
        self._clear("대시보드")
        stats = tk.Frame(self.content, bg=COLORS["bg"])
        stats.pack(fill="x")
        for index in range(4):
            stats.columnconfigure(index, weight=1)
        novels = self.factory.list_novels()
        references = self.factory.list_references()
        analyzed = sum(item["status"] == "ANALYZED" for item in references)
        self._card(stats, "등록 작품", str(len(novels)), "장편 프로젝트", 0)
        self._card(stats, "참고소설", str(len(references)), f"분석 완료 {analyzed}편", 1)
        self._card(stats, "분석 대기", str(len(references) - analyzed), "로컬 분석 엔진", 2)
        self._card(stats, "저장 위치", "LOCAL", "외부 전송 없음", 3)
        panel = self._panel(self.content, "빠른 시작", "참고소설을 분석하거나 새 장편 프로젝트를 만드세요.")
        panel.pack(fill="both", expand=True, pady=(20, 0))
        actions = tk.Frame(panel, bg=COLORS["surface"])
        actions.pack(anchor="w", padx=24, pady=25)
        self._button(actions, "새 작품 만들기", self._new_novel_dialog).pack(side="left", padx=(0, 10))
        self._button(actions, "참고소설 가져오기", self._import_reference, secondary=True).pack(side="left")
        guide = "1. 참고소설을 파일로 가져와 구조를 분석합니다.\n\n2. 새 작품의 Novel Bible을 만듭니다.\n\n3. 참고할 구조와 강도를 작품에 연결합니다.\n\n4. 캐릭터·복선·시간선을 등록하고 회차를 설계합니다.\n\n5. 완성 원고를 검사해 유사성과 반복 표현을 차단합니다."
        tk.Label(panel, text=guide, justify="left", bg=COLORS["surface"], fg=COLORS["muted"],
                 font=("Malgun Gothic", 10)).pack(anchor="w", padx=25)

    def show_references(self) -> None:
        self._clear("참고소설 분석")
        bar = tk.Frame(self.content, bg=COLORS["bg"])
        bar.pack(fill="x", pady=(0, 14))
        self._button(bar, "파일 가져오기", self._import_reference).pack(side="right")
        tree = ttk.Treeview(self.content, columns=("title", "format", "episodes", "dialogue", "speed", "status"), show="headings")
        labels = ("작품", "형식", "회차", "대사 비율", "전개", "상태")
        for name, label in zip(tree["columns"], labels):
            tree.heading(name, text=label)
            tree.column(name, width=140 if name == "title" else 85, anchor="center")
        for item in self.factory.list_references():
            profile = item.get("profile") or {}
            tree.insert("", "end", iid=item["id"], values=(item["title"], item["source_format"].upper(),
                        profile.get("episode_count", "-"), self._percent(profile.get("dialogue_ratio")),
                        profile.get("plot_speed", "-"), item["status"]))
        tree.pack(fill="both", expand=True)
        menu = tk.Frame(self.content, bg=COLORS["bg"])
        menu.pack(fill="x", pady=(12, 0))
        self._button(menu, "선택 작품 분석", lambda: self._analyze_selected(tree)).pack(side="left")
        self._button(menu, "분석 결과 보기", lambda: self._show_reference_profile(tree), secondary=True).pack(side="left", padx=8)
        self._button(menu, "현재 작품에 연결", lambda: self._link_selected_reference(tree), secondary=True).pack(side="left")

    def show_novels(self) -> None:
        self._clear("작품 관리")
        top = tk.Frame(self.content, bg=COLORS["bg"]); top.pack(fill="x", pady=(0, 14))
        self._button(top, "새 작품", self._new_novel_dialog).pack(side="right")
        tree = ttk.Treeview(self.content, columns=("title", "genre", "episodes", "length", "status"), show="headings")
        for name, label, width in (("title", "제목", 260), ("genre", "장르", 120), ("episodes", "목표 회차", 100),
                                    ("length", "회차당 글자", 110), ("status", "상태", 100)):
            tree.heading(name, text=label); tree.column(name, width=width, anchor="center")
        for item in self.factory.list_novels():
            tree.insert("", "end", iid=item["id"], values=(item["title"], item["genre"], item["target_episodes"],
                        item["characters_per_episode"], item["status"]))
        tree.pack(fill="both", expand=True)
        tree.bind("<Double-1>", lambda _: self._choose_tree_novel(tree))
        self._button(self.content, "선택 작품 사용", lambda: self._choose_tree_novel(tree), secondary=True).pack(anchor="w", pady=12)

    def show_memory(self) -> None:
        self._clear("캐릭터·장기 기억")
        if not self._require_novel(): return
        tabs = ttk.Notebook(self.content); tabs.pack(fill="both", expand=True)
        character_tab = tk.Frame(tabs, bg=COLORS["surface"]); timeline_tab = tk.Frame(tabs, bg=COLORS["surface"])
        shadow_tab = tk.Frame(tabs, bg=COLORS["surface"])
        tabs.add(character_tab, text="  캐릭터  "); tabs.add(timeline_tab, text="  타임라인  "); tabs.add(shadow_tab, text="  복선  ")
        self._memory_tab(character_tab, "캐릭터 추가", self._new_character_dialog,
                         "인물별 성격, 말투, 목표와 알고 있는 정보를 분리해서 저장합니다.")
        self._memory_tab(timeline_tab, "사건 추가", self._new_timeline_dialog,
                         "작품 내부 날짜와 사건 발생 회차를 저장해 시간 오류를 방지합니다.")
        self._memory_tab(shadow_tab, "복선 추가", self._new_foreshadow_dialog,
                         "복선 설치 회차, 설명, 예정 회수 회차와 상태를 관리합니다.")

    def show_episodes(self) -> None:
        self._clear("회차 제작")
        if not self._require_novel(): return
        form = self._panel(self.content, "Episode Planner", "회차별 목적과 사건, Hook을 설계해 DB에 저장합니다.")
        form.pack(fill="both", expand=True)
        entries = {}
        for row, (key, label) in enumerate((("number", "회차 번호"), ("title", "회차 제목"), ("purpose", "이번 화 목적"),
                                             ("characters", "등장인물 (쉼표 구분)"), ("conflict", "핵심 갈등"), ("hook", "마지막 Hook"))):
            tk.Label(form, text=label, bg=COLORS["surface"], fg=COLORS["text"], font=("Malgun Gothic", 9, "bold")).grid(row=row, column=0, sticky="w", padx=25, pady=9)
            entry = ttk.Entry(form, width=70); entry.grid(row=row, column=1, sticky="ew", padx=(0, 25), pady=9); entries[key] = entry
        form.columnconfigure(1, weight=1)
        self._button(form, "회차 계획 저장", lambda: self._save_episode(entries)).grid(row=7, column=1, sticky="e", padx=25, pady=20)
        ai_actions = tk.Frame(form, bg=COLORS["surface"])
        ai_actions.grid(row=8, column=1, sticky="e", padx=25, pady=(0, 20))
        self._button(ai_actions, "AI 연결 설정", self._configure_ai, secondary=True).pack(side="left", padx=(0, 8))
        self._button(ai_actions, "AI로 이 회차 자동 제작", lambda: self._generate_episode(entries)).pack(side="left")

    def show_quality(self) -> None:
        self._clear("품질 검사")
        if not self._require_novel(): return
        panel = self._panel(self.content, "원고 검사", "분량·반복 표현·참고작 유사성·대사 비율을 검사하고 통과한 원고를 확정합니다.")
        panel.pack(fill="both", expand=True)
        line = tk.Frame(panel, bg=COLORS["surface"]); line.pack(fill="x", padx=24, pady=14)
        tk.Label(line, text="회차", bg=COLORS["surface"], font=("Malgun Gothic", 9, "bold")).pack(side="left")
        number = ttk.Entry(line, width=8); number.pack(side="left", padx=8)
        manuscript = tk.Text(panel, wrap="word", relief="solid", borderwidth=1, font=("Malgun Gothic", 10), undo=True)
        manuscript.pack(fill="both", expand=True, padx=24, pady=(0, 12))
        result = tk.Label(panel, text="", justify="left", bg=COLORS["surface"], fg=COLORS["muted"], font=("Malgun Gothic", 9))
        result.pack(anchor="w", padx=24)
        self._button(panel, "검사 및 원고 확정", lambda: self._finalize(number, manuscript, result)).pack(anchor="e", padx=24, pady=16)

    def show_publishing(self) -> None:
        self._clear("EPUB·출판")
        if not self._require_novel(): return
        audit = self.factory.completion_audit(self.selected_novel_id)
        panel = self._panel(self.content, "완결 검사", "EPUB 생성 전 누락 회차, 수정 필요 원고와 열린 복선을 확인합니다.")
        panel.pack(fill="both", expand=True)
        status_text = "완결 조건 통과" if audit["can_complete"] else "아직 완결할 수 없습니다"
        status_color = COLORS["success"] if audit["can_complete"] else COLORS["warning"]
        tk.Label(panel, text=status_text, bg=COLORS["surface"], fg=status_color,
                 font=("Malgun Gothic", 17, "bold")).pack(anchor="w", padx=24, pady=(24, 5))
        tk.Label(panel, text=f"확정 회차 {audit['final_episode_count']} / 목표 {audit['target_episode_count']}",
                 bg=COLORS["surface"], fg=COLORS["muted"], font=("Malgun Gothic", 10)).pack(anchor="w", padx=24)
        issue_box = tk.Text(panel, height=14, wrap="word", relief="solid", borderwidth=1, font=("Malgun Gothic", 9))
        issue_box.pack(fill="both", expand=True, padx=24, pady=18)
        if audit["issues"]:
            names = {"MISSING_EPISODES": "누락된 확정 회차", "REVISION_REQUIRED": "수정 필요 회차", "OPEN_FORESHADOWING": "미회수 복선"}
            for issue in audit["issues"]:
                issue_box.insert("end", f"• {names.get(issue['type'], issue['type'])}: {issue['count']}건\n")
        else:
            issue_box.insert("end", "모든 회차와 복선 검사가 완료되었습니다.\n")
        issue_box.config(state="disabled")
        controls = tk.Frame(panel, bg=COLORS["surface"]); controls.pack(fill="x", padx=24, pady=(0, 22))
        tk.Label(controls, text="저자명", bg=COLORS["surface"], fg=COLORS["text"]).pack(side="left")
        author = ttk.Entry(controls, width=24); author.insert(0, "AI Novel Factory"); author.pack(side="left", padx=8)
        self._button(controls, "EPUB 내보내기", lambda: self._export_epub(author.get().strip())).pack(side="right")

    def _export_epub(self, author: str) -> None:
        novel = self.factory.get_novel(self.selected_novel_id)
        path = filedialog.asksaveasfilename(title="EPUB 저장", initialfile=f"{novel['title']}.epub",
                                            defaultextension=".epub", filetypes=[("EPUB 전자책", "*.epub")])
        if not path: return
        try:
            output = self.factory.export_epub(self.selected_novel_id, path, author or "AI Novel Factory")
            messagebox.showinfo("EPUB 생성 완료", f"전자책을 저장했습니다.\n{output}")
        except Exception as exc:
            messagebox.showerror("EPUB 생성 실패", str(exc))

    def _panel(self, parent: tk.Widget, title: str, subtitle: str) -> tk.Frame:
        panel = tk.Frame(parent, bg=COLORS["surface"], highlightbackground=COLORS["line"], highlightthickness=1)
        tk.Label(panel, text=title, bg=COLORS["surface"], fg=COLORS["text"], font=("Malgun Gothic", 14, "bold")).pack(anchor="w", padx=24, pady=(20, 3))
        tk.Label(panel, text=subtitle, bg=COLORS["surface"], fg=COLORS["muted"], font=("Malgun Gothic", 9)).pack(anchor="w", padx=24)
        return panel

    def _button(self, parent: tk.Widget, text: str, command: Callable, secondary: bool = False) -> tk.Button:
        return tk.Button(parent, text=text, command=command, relief="flat", borderwidth=0, cursor="hand2",
                         bg=COLORS["surface"] if secondary else COLORS["primary"],
                         fg=COLORS["primary"] if secondary else "white",
                         activebackground="#eeeafd" if secondary else COLORS["primary_dark"],
                         activeforeground=COLORS["primary" if secondary else "surface"],
                         highlightbackground=COLORS["line"], highlightthickness=1, font=("Malgun Gothic", 9, "bold"), padx=16, pady=8)

    def _memory_tab(self, tab: tk.Frame, button_text: str, command: Callable, help_text: str) -> None:
        tk.Label(tab, text=help_text, bg=COLORS["surface"], fg=COLORS["muted"], font=("Malgun Gothic", 10)).pack(pady=(50, 20))
        self._button(tab, button_text, command).pack()

    def _require_novel(self) -> bool:
        if self.selected_novel_id: return True
        tk.Label(self.content, text="먼저 작품을 만들어 주세요.", bg=COLORS["bg"], fg=COLORS["muted"], font=("Malgun Gothic", 13)).pack(pady=80)
        return False

    def _new_novel_dialog(self) -> None:
        fields = self._form_dialog("새 작품 만들기", (("title", "작품 제목"), ("genre", "장르"), ("premise", "로그라인"),
                                                        ("episodes", "목표 회차 (기본 250)"), ("length", "회차당 글자 (기본 5000)"), ("atmosphere", "분위기")))
        if not fields: return
        try:
            novel = self.factory.create_novel({"title": fields["title"], "genre": fields["genre"], "premise": fields["premise"],
                "target_episodes": int(fields["episodes"] or 250), "characters_per_episode": int(fields["length"] or 5000), "atmosphere": fields["atmosphere"]})
            self.selected_novel_id = novel["id"]; messagebox.showinfo("완료", "Novel Bible을 생성했습니다."); self.show_novels()
        except (ValueError, KeyError) as exc: messagebox.showerror("입력 오류", str(exc))

    def _import_reference(self) -> None:
        path = filedialog.askopenfilename(title="참고소설 선택", filetypes=[("지원 문서", "*.txt *.md *.docx *.epub *.pdf"), ("모든 파일", "*.*")])
        if not path: return
        title = self._ask("참고소설 제목", "작품 제목", Path(path).stem)
        if not title: return
        try:
            record = self.factory.register_reference(title, path)
        except Exception as exc: messagebox.showerror("등록 실패", str(exc)); return
        self._run_background(lambda: self.factory.analyze_reference(record["id"]), self._analysis_finished)

    def _analyze_selected(self, tree: ttk.Treeview) -> None:
        selection = tree.selection()
        if not selection: messagebox.showwarning("선택 필요", "분석할 참고소설을 선택하세요."); return
        self._run_background(lambda: self.factory.analyze_reference(selection[0]), self._analysis_finished)

    def _analysis_finished(self, result: Any) -> None:
        if isinstance(result, Exception): messagebox.showerror("분석 실패", str(result))
        else: messagebox.showinfo("분석 완료", f"{result['title']}의 Reference Profile을 생성했습니다.")
        self.show_references()

    def _show_reference_profile(self, tree: ttk.Treeview) -> None:
        selection = tree.selection()
        if not selection: messagebox.showwarning("선택 필요", "결과를 확인할 작품을 선택하세요."); return
        item = self.factory.get_reference(selection[0])
        if not item["profile"]: messagebox.showwarning("미분석", "먼저 분석을 실행하세요."); return
        self._text_window(item["title"] + " · Reference Profile", json.dumps(item["profile"], ensure_ascii=False, indent=2))

    def _link_selected_reference(self, tree: ttk.Treeview) -> None:
        selection = tree.selection()
        if not selection:
            messagebox.showwarning("선택 필요", "현재 작품에 연결할 참고소설을 선택하세요.")
            return
        if not self.selected_novel_id:
            messagebox.showwarning("작품 필요", "먼저 작품을 만들고 상단에서 선택하세요.")
            return
        values = self._form_dialog("참고 강도 설정", (("pacing", "전개 속도 (0~1)"), ("episode_structure", "회차 구조 (0~1)"),
                                                     ("cliffhanger", "클리프행어 (0~1)"), ("foreshadowing", "복선 (0~1)"),
                                                     ("character_structure", "캐릭터 구조 (0~1)"), ("style", "문체 (권장 0)")))
        if not values:
            return
        try:
            weights = {key: float(value or 0) for key, value in values.items()}
            self.factory.link_reference(self.selected_novel_id, selection[0], weights)
            messagebox.showinfo("연결 완료", "구조 분석 데이터만 현재 작품에 연결했습니다.")
        except Exception as exc:
            messagebox.showerror("연결 실패", str(exc))

    def _choose_tree_novel(self, tree: ttk.Treeview) -> None:
        selection = tree.selection()
        if selection: self.selected_novel_id = selection[0]; self._refresh_novel_picker(); messagebox.showinfo("선택 완료", "현재 작업 작품을 변경했습니다.")

    def _new_character_dialog(self) -> None:
        values = self._form_dialog("캐릭터 추가", (("name", "이름"), ("age", "나이"), ("job", "직업"), ("personality", "성격 (쉼표 구분)"),
                                                       ("speech", "말투"), ("knowledge", "알고 있는 정보 (쉼표 구분)"), ("goals", "목표 (쉼표 구분)")))
        if values:
            self.factory.add_character(self.selected_novel_id, {"name": values["name"], "age": int(values["age"]) if values["age"] else None,
                "job": values["job"], "personality": self._csv(values["personality"]), "speech_style": values["speech"],
                "knowledge": self._csv(values["knowledge"]), "goals": self._csv(values["goals"])}); messagebox.showinfo("저장", "캐릭터를 저장했습니다.")

    def _new_timeline_dialog(self) -> None:
        values = self._form_dialog("타임라인 사건 추가", (("episode", "회차"), ("date", "작품 내부 날짜/상대시간"), ("description", "사건")))
        if values:
            self.factory.add_timeline_event(self.selected_novel_id, {"episode": int(values["episode"]), "occurred_at": values["date"], "description": values["description"]}); messagebox.showinfo("저장", "타임라인 사건을 저장했습니다.")

    def _new_foreshadow_dialog(self) -> None:
        values = self._form_dialog("복선 추가", (("setup", "설치 회차"), ("description", "복선 설명"), ("payoff", "예정 회수 회차")))
        if values:
            self.factory.add_foreshadowing(self.selected_novel_id, {"setup_episode": int(values["setup"]), "description": values["description"], "planned_payoff": int(values["payoff"]) if values["payoff"] else None}); messagebox.showinfo("저장", "복선을 저장했습니다.")

    def _save_episode(self, entries: dict[str, ttk.Entry]) -> None:
        try:
            values = {key: entry.get().strip() for key, entry in entries.items()}
            self.factory.plan_episode(self.selected_novel_id, int(values["number"]), {"title": values["title"], "purpose": values["purpose"],
                "characters": self._csv(values["characters"]), "conflict": values["conflict"], "hook": values["hook"]})
            messagebox.showinfo("저장 완료", f"{values['number']}화 계획을 저장했습니다.")
        except Exception as exc: messagebox.showerror("저장 실패", str(exc))

    def _configure_ai(self) -> None:
        dialog = tk.Toplevel(self)
        dialog.title("AI 연결 설정")
        dialog.configure(bg=COLORS["surface"])
        dialog.transient(self)
        dialog.grab_set()
        values = (("endpoint", "호환 API 주소", self.ai_endpoint, False),
                  ("model", "모델", self.ai_model, False), ("key", "API 키", self.ai_key, True))
        entries: dict[str, ttk.Entry] = {}
        for row, (name, label, value, secret) in enumerate(values):
            tk.Label(dialog, text=label, bg=COLORS["surface"], fg=COLORS["text"],
                     font=("Malgun Gothic", 9)).grid(row=row, column=0, sticky="w", padx=20, pady=10)
            entry = ttk.Entry(dialog, width=62, show="*" if secret else "")
            entry.insert(0, value)
            entry.grid(row=row, column=1, padx=20, pady=10)
            entries[name] = entry

        def save() -> None:
            self.ai_endpoint = entries["endpoint"].get().strip()
            self.ai_model = entries["model"].get().strip()
            self.ai_key = entries["key"].get().strip()
            if not all((self.ai_endpoint, self.ai_model, self.ai_key)):
                messagebox.showwarning("필수 입력", "API 주소, 모델과 API 키를 모두 입력하세요.", parent=dialog)
                return
            dialog.destroy()
            messagebox.showinfo("설정 완료", "API 키는 현재 실행 중인 메모리에만 보관되며 파일로 저장하지 않습니다.")

        self._button(dialog, "설정 적용", save).grid(row=len(values), column=1, sticky="e", padx=20, pady=18)
        dialog.wait_window()

    def _generate_episode(self, entries: dict[str, ttk.Entry]) -> None:
        if not self.ai_key:
            self._configure_ai()
        if not self.ai_key:
            return
        try:
            number = int(entries["number"].get().strip())
        except ValueError:
            messagebox.showerror("입력 오류", "자동 제작할 회차 번호를 입력하세요.")
            return
        progress_window = tk.Toplevel(self)
        progress_window.title("AI 회차 제작")
        progress_window.geometry("430x145")
        progress_window.configure(bg=COLORS["surface"])
        progress_window.transient(self)
        status = tk.Label(progress_window, text="컨텍스트를 준비하고 있습니다...", bg=COLORS["surface"],
                          fg=COLORS["text"], font=("Malgun Gothic", 10))
        status.pack(pady=(25, 12))
        bar = ttk.Progressbar(progress_window, maximum=100, length=350)
        bar.pack()

        def update(stage: str, percent: int) -> None:
            def apply_progress(value: tuple[str, int]) -> None:
                current_stage, current_percent = value
                if progress_window.winfo_exists():
                    status.config(text=current_stage)
                    bar.config(value=current_percent)
            self._jobs.put((lambda s=stage, p=percent: (s, p), apply_progress))

        provider = CompatibleChatProvider(self.ai_key, self.ai_model, self.ai_endpoint)
        orchestrator = EpisodeOrchestrator(self.factory, provider)

        def finished(result: Any) -> None:
            progress_window.destroy()
            if isinstance(result, Exception):
                messagebox.showerror("자동 제작 실패", str(result))
                return
            episode = result.episode
            report = episode["quality"]
            messagebox.showinfo("자동 제작 완료", f"{number}화 · 상태 {episode['status']} · 품질 {report['score']:.0f}점\nAI 호출 {result.attempts + 1}회")

        self._run_background(lambda: orchestrator.generate_episode(self.selected_novel_id, number, update), finished)

    def _finalize(self, number: ttk.Entry, manuscript: tk.Text, result: tk.Label) -> None:
        try:
            episode = self.factory.finalize_episode(self.selected_novel_id, int(number.get()), manuscript.get("1.0", "end-1c"))
            report = episode["quality"]
            issues = "\n".join(f"• [{issue['severity']}] {issue['message']}" for issue in report["issues"]) or "• 발견된 문제가 없습니다."
            result.config(text=f"점수 {report['score']:.0f}/100 · {'통과' if report['passed'] else '수정 필요'}\n{issues}", fg=COLORS["success"] if report["passed"] else COLORS["danger"])
        except Exception as exc: messagebox.showerror("검사 실패", str(exc))

    def _form_dialog(self, title: str, fields: tuple[tuple[str, str], ...]) -> dict[str, str] | None:
        dialog = tk.Toplevel(self); dialog.title(title); dialog.configure(bg=COLORS["surface"]); dialog.transient(self); dialog.grab_set(); dialog.resizable(False, False)
        entries: dict[str, ttk.Entry] = {}; result: dict[str, str] = {}
        for row, (key, label) in enumerate(fields):
            tk.Label(dialog, text=label, bg=COLORS["surface"], fg=COLORS["text"], font=("Malgun Gothic", 9)).grid(row=row, column=0, sticky="w", padx=20, pady=9)
            entry = ttk.Entry(dialog, width=45); entry.grid(row=row, column=1, padx=20, pady=9); entries[key] = entry
        def submit():
            result.update({key: entry.get().strip() for key, entry in entries.items()})
            if not result.get(next(iter(fields))[0]): messagebox.showwarning("필수 입력", "첫 번째 항목을 입력하세요.", parent=dialog); result.clear(); return
            dialog.destroy()
        self._button(dialog, "저장", submit).grid(row=len(fields), column=1, sticky="e", padx=20, pady=18)
        dialog.wait_window(); return result or None

    def _ask(self, title: str, label: str, default: str) -> str | None:
        return simpledialog.askstring(title, label, initialvalue=default, parent=self)

    def _text_window(self, title: str, content: str) -> None:
        window = tk.Toplevel(self); window.title(title); window.geometry("700x600")
        text = tk.Text(window, wrap="word", padx=15, pady=15, font=("Consolas", 10)); text.insert("1.0", content); text.config(state="disabled"); text.pack(fill="both", expand=True)

    def _run_background(self, work: Callable[[], Any], callback: Callable[[Any], None]) -> None:
        def runner():
            try: result = work()
            except Exception as exc: result = exc
            self._jobs.put((lambda: result, callback))
        threading.Thread(target=runner, daemon=True).start()

    def _poll_jobs(self) -> None:
        try:
            while True:
                get_result, callback = self._jobs.get_nowait(); callback(get_result())
        except queue.Empty: pass
        self.after(100, self._poll_jobs)

    @staticmethod
    def _csv(value: str) -> list[str]: return [item.strip() for item in value.split(",") if item.strip()]

    @staticmethod
    def _percent(value: float | None) -> str: return f"{value * 100:.1f}%" if value is not None else "-"


def main(factory: NovelFactory | None = None) -> None:
    app = NovelFactoryApp(factory)
    app.mainloop()


if __name__ == "__main__":
    main()
