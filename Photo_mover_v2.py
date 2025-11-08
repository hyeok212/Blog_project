import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import os
import shutil
import random
import json
# import datetime # 필요시 타임스탬프 파일명 제안에 사용 가능

# 지원할 사진 확장자 목록
PHOTO_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp']

class PhotoOrganizerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("블로그 사진 자동 정리 도구")
        self.root.geometry("700x880")

        self.sources = []
        self.targets = []
        self.filename_option = tk.StringVar(value="category_prefix")
        self.selection_mode_option = tk.StringVar(value="sequential")

        # --- 스타일 설정 ---
        style = ttk.Style()
        style.configure("TLabel", padding=5, font=('Helvetica', 10))
        style.configure("TButton", padding=5, font=('Helvetica', 10))
        style.configure("TEntry", padding=5, font=('Helvetica', 10))
        style.configure("TRadiobutton", padding=5, font=('Helvetica', 10))
        style.configure("Treeview.Heading", font=('Helvetica', 10, 'bold'))

        # --- UI 구성 ---
        # 소스 폴더 설정
        source_frame = ttk.LabelFrame(root, text="소스 폴더 설정", padding=10)
        source_frame.pack(fill="x", padx=10, pady=5)
        self.source_tree = ttk.Treeview(source_frame, columns=("path", "count"), show="headings", height=5)
        self.source_tree.heading("path", text="소스 폴더 경로")
        self.source_tree.heading("count", text="가져올 수량")
        self.source_tree.column("path", width=400)
        self.source_tree.column("count", width=100, anchor="center")
        self.source_tree.pack(fill="x", expand=True, pady=5)
        source_input_frame = ttk.Frame(source_frame)
        source_input_frame.pack(fill="x")
        ttk.Label(source_input_frame, text="경로:").pack(side=tk.LEFT, padx=(0,5))
        self.source_path_entry = ttk.Entry(source_input_frame, width=40)
        self.source_path_entry.pack(side=tk.LEFT, expand=True, fill="x")
        ttk.Button(source_input_frame, text="폴더찾기...", command=self.browse_source_folder).pack(side=tk.LEFT, padx=5)
        ttk.Label(source_input_frame, text="수량:").pack(side=tk.LEFT, padx=(10,5))
        self.source_count_entry = ttk.Entry(source_input_frame, width=5)
        self.source_count_entry.pack(side=tk.LEFT)
        source_button_frame = ttk.Frame(source_frame)
        source_button_frame.pack(fill="x", pady=5)
        ttk.Button(source_button_frame, text="소스 추가", command=self.add_source).pack(side=tk.LEFT, padx=5)
        ttk.Button(source_button_frame, text="선택 삭제", command=self.remove_source).pack(side=tk.LEFT)

        # 타겟 폴더 설정
        target_frame = ttk.LabelFrame(root, text="타겟 폴더 설정 (포스팅별 목적지)", padding=10)
        target_frame.pack(fill="x", padx=10, pady=5)
        self.target_listbox = tk.Listbox(target_frame, height=5, font=('Helvetica', 10))
        self.target_listbox.pack(fill="x", expand=True, pady=5)
        target_input_frame = ttk.Frame(target_frame)
        target_input_frame.pack(fill="x")
        ttk.Label(target_input_frame, text="경로:").pack(side=tk.LEFT, padx=(0,5))
        self.target_path_entry = ttk.Entry(target_input_frame, width=50)
        self.target_path_entry.pack(side=tk.LEFT, expand=True, fill="x")
        ttk.Button(target_input_frame, text="폴더찾기...", command=self.browse_target_folder).pack(side=tk.LEFT, padx=5)
        target_button_frame = ttk.Frame(target_frame)
        target_button_frame.pack(fill="x", pady=5)
        ttk.Button(target_button_frame, text="타겟 추가", command=self.add_target).pack(side=tk.LEFT, padx=5)
        ttk.Button(target_button_frame, text="선택 삭제", command=self.remove_target).pack(side=tk.LEFT)
        
        # 타겟 폴더만 저장/불러오기 버튼 추가
        target_save_load_frame = ttk.Frame(target_frame)
        target_save_load_frame.pack(fill="x", pady=5)
        ttk.Button(target_save_load_frame, text="타겟 폴더만 저장", 
                  command=self.save_targets_only).pack(side=tk.LEFT, padx=5)
        ttk.Button(target_save_load_frame, text="타겟 폴더만 불러오기", 
                  command=self.load_targets_only).pack(side=tk.LEFT)

        # 파일 이름 처리 방식
        naming_frame = ttk.LabelFrame(root, text="파일 이름 처리 방식", padding=10)
        naming_frame.pack(fill="x", padx=10, pady=5)
        ttk.Radiobutton(naming_frame, text="카테고리명_원본파일명 (예: 내부사진_IMG01.jpg)",
                        variable=self.filename_option, value="category_prefix").pack(anchor="w")
        ttk.Radiobutton(naming_frame, text="원본파일명_숫자 (예: IMG01_1.jpg)",
                        variable=self.filename_option, value="original_number").pack(anchor="w")
        ttk.Radiobutton(naming_frame, text="카테고리명+순번 (예: 계란말이1.jpg)",
                        variable=self.filename_option, value="category_sequential").pack(anchor="w")

        # 사진 추출 방식
        selection_mode_frame = ttk.LabelFrame(root, text="사진 추출 방식", padding=10)
        selection_mode_frame.pack(fill="x", padx=10, pady=5)
        ttk.Radiobutton(selection_mode_frame, text="정렬된 순서대로 추출",
                variable=self.selection_mode_option, value="sequential").pack(anchor="w")
        ttk.Radiobutton(selection_mode_frame, text="무작위(랜덤)로 추출",
                variable=self.selection_mode_option, value="random").pack(anchor="w")

        # 실행 버튼
        ttk.Button(root, text="✨ 실행 ✨", command=self.execute_processing, style="Accent.TButton").pack(pady=15, ipady=5)
        style.configure("Accent.TButton", font=('Helvetica', 12, 'bold'))

        # 전체 설정 저장/불러오기 버튼
        settings_button_frame = ttk.Frame(root)
        settings_button_frame.pack(fill="x", padx=10, pady=5)
        ttk.Button(settings_button_frame, text="설정 저장", command=self.save_settings).pack(side=tk.LEFT, padx=5)
        ttk.Button(settings_button_frame, text="설정 불러오기", command=self.load_settings).pack(side=tk.LEFT)

        # 상태 표시
        self.status_label = ttk.Label(root, text="준비 완료. 설정을 불러오거나 새로 만드세요.", relief=tk.SUNKEN, anchor="w", padding=5)
        self.status_label.pack(side=tk.BOTTOM, fill="x")

    def browse_source_folder(self):
        path = filedialog.askdirectory()
        if path:
            self.source_path_entry.delete(0, tk.END)
            self.source_path_entry.insert(0, path)

    def browse_target_folder(self):
        path = filedialog.askdirectory()
        if path:
            self.target_path_entry.delete(0, tk.END)
            self.target_path_entry.insert(0, path)

    def add_source(self):
        path = self.source_path_entry.get()
        count_str = self.source_count_entry.get()
        if not path or not count_str:
            messagebox.showwarning("입력 오류", "소스 폴더 경로와 수량을 모두 입력해주세요.")
            return
        if not os.path.isdir(path):
            messagebox.showwarning("경로 오류", f"존재하지 않는 소스 폴더 경로입니다: {path}")
            return
        try:
            count = int(count_str)
            if count <= 0: raise ValueError
        except ValueError:
            messagebox.showwarning("입력 오류", "수량은 0보다 큰 숫자로 입력해주세요.")
            return
        for item in self.sources:
            if item['path'] == path:
                messagebox.showwarning("중복 오류", f"이미 추가된 소스 폴더입니다: {path}")
                return
        self.sources.append({'path': path, 'count': count})
        self.source_tree.insert("", tk.END, values=(path, count))
        self.source_path_entry.delete(0, tk.END)
        self.source_count_entry.delete(0, tk.END)
        self.update_status(f"소스 폴더 추가됨: {os.path.basename(path)}")

    def remove_source(self):
        selected_item = self.source_tree.selection()
        if not selected_item:
            messagebox.showwarning("선택 오류", "삭제할 소스 폴더를 목록에서 선택해주세요.")
            return
        item_values = self.source_tree.item(selected_item[0], "values")
        path_to_remove = item_values[0]
        self.sources = [s for s in self.sources if s['path'] != path_to_remove]
        self.source_tree.delete(selected_item[0])
        self.update_status(f"소스 폴더 삭제됨: {os.path.basename(path_to_remove)}")

    def add_target(self):
        path = self.target_path_entry.get()
        if not path:
            messagebox.showwarning("입력 오류", "타겟 폴더 경로를 입력해주세요.")
            return
        if not os.path.isdir(path):
            if messagebox.askyesno("폴더 생성", f"타겟 폴더가 존재하지 않습니다:\n{path}\n\n새로 생성하시겠습니까?"):
                try:
                    os.makedirs(path, exist_ok=True)
                    self.update_status(f"타겟 폴더 생성됨: {path}")
                except OSError as e:
                    messagebox.showerror("생성 실패", f"타겟 폴더 생성에 실패했습니다: {e}")
                    return
            else:
                return
        if path in self.targets:
            messagebox.showwarning("중복 오류", f"이미 추가된 타겟 폴더입니다: {path}")
            return
        self.targets.append(path)
        self.target_listbox.insert(tk.END, path)
        self.target_path_entry.delete(0, tk.END)
        self.update_status(f"타겟 폴더 추가됨: {os.path.basename(path)}")

    def remove_target(self):
        selected_indices = self.target_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("선택 오류", "삭제할 타겟 폴더를 목록에서 선택해주세요.")
            return
        path_to_remove = self.target_listbox.get(selected_indices[0])
        self.targets.remove(path_to_remove)
        self.target_listbox.delete(selected_indices[0])
        self.update_status(f"타겟 폴더 삭제됨: {os.path.basename(path_to_remove)}")

    def update_status(self, message):
        self.status_label.config(text=message)
        self.root.update_idletasks()
        
    def get_available_photos(self, folder_path, count):
        photos_in_folder = []
        try:
            all_files = os.listdir(folder_path)
            for filename in all_files:
                if any(filename.lower().endswith(ext) for ext in PHOTO_EXTENSIONS):
                    photos_in_folder.append(os.path.join(folder_path, filename))
        except FileNotFoundError:
            self.update_status(f"오류: 소스 폴더를 찾을 수 없습니다 - {folder_path}")
            return []
        except Exception as e:
            self.update_status(f"오류: {folder_path} 파일 읽기 중 오류 - {e}")
            return []

        if not photos_in_folder:
            return []

        current_selection_mode = self.selection_mode_option.get()

        if len(photos_in_folder) < count:
            self.update_status(f"경고: {os.path.basename(folder_path)} 폴더에 사진이 {len(photos_in_folder)}장만 있어 요청된 {count}장보다 적습니다. 있는 사진만 가져옵니다.")
            if current_selection_mode == "random":
                random.shuffle(photos_in_folder)
            else: # sequential
                photos_in_folder.sort()
            return photos_in_folder

        if current_selection_mode == "random":
            return random.sample(photos_in_folder, count)
        else: # sequential
            photos_in_folder.sort()
            return photos_in_folder[:count]

    def generate_new_filename(self, original_filepath, category_name, target_folder):
        original_filename = os.path.basename(original_filepath)
        name_part, ext_part = os.path.splitext(original_filename)
        
        option = self.filename_option.get()
        new_filename = original_filename 

        if option == "category_prefix":
            new_filename = f"{category_name}_{original_filename}"
        elif option == "original_number":
            counter = 1
            if not os.path.exists(os.path.join(target_folder, original_filename)):
                new_filename = original_filename
            else:
                new_filename = f"{name_part}_{counter}{ext_part}"
                while os.path.exists(os.path.join(target_folder, new_filename)):
                    counter += 1
                    new_filename = f"{name_part}_{counter}{ext_part}"
        elif option == "category_sequential":
            number = 1
            new_filename_base = category_name
            new_filename = f"{new_filename_base}{number}{ext_part}"
            while os.path.exists(os.path.join(target_folder, new_filename)):
                number += 1
                new_filename = f"{new_filename_base}{number}{ext_part}"
        return new_filename
        
    def execute_processing(self):
        if not self.sources:
            messagebox.showerror("오류", "소스 폴더가 하나 이상 필요합니다.")
            return
        if not self.targets:
            messagebox.showerror("오류", "타겟 폴더가 하나 이상 필요합니다.")
            return

        self.update_status("사진 정리 작업 시작...")
        processed_targets = 0
        total_files_moved = 0

        for target_idx, target_path in enumerate(self.targets):
            self.update_status(f"'{os.path.basename(target_path)}' 폴더 작업 중... ({target_idx + 1}/{len(self.targets)})")
            if not os.path.exists(target_path):
                try:
                    os.makedirs(target_path, exist_ok=True)
                except OSError as e:
                    messagebox.showerror("오류", f"타겟 폴더 생성 실패: {target_path}\n{e}")
                    continue

            files_in_current_target = 0
            current_sources_snapshot = [src.copy() for src in self.sources]

            for source_info in current_sources_snapshot:
                source_folder_path = source_info['path']
                files_to_take = source_info['count']
                category_name = os.path.basename(source_folder_path)

                photos_to_move = self.get_available_photos(source_folder_path, files_to_take)

                if not photos_to_move:
                    self.update_status(f"정보: '{category_name}' 폴더에서 '{os.path.basename(target_path)}'로 가져올 사진이 없습니다.")
                    continue

                for photo_path in photos_to_move:
                    try:
                        new_filename = self.generate_new_filename(photo_path, category_name, target_path)
                        destination_path = os.path.join(target_path, new_filename)
                        
                        shutil.move(photo_path, destination_path)
                        total_files_moved += 1
                        files_in_current_target +=1
                        self.update_status(f"이동: {os.path.basename(photo_path)} -> {os.path.join(os.path.basename(target_path), new_filename)}")
                    except FileNotFoundError:
                        self.update_status(f"경고: 이동하려던 파일 '{os.path.basename(photo_path)}'을(를) 찾을 수 없습니다. 건너뜁니다.")
                        continue
                    except Exception as e:
                        messagebox.showerror("이동 오류", f"파일 이동 중 오류 발생:\n{photo_path} -> {target_path}\n{e}")
                        continue 
            
            self.update_status(f"'{os.path.basename(target_path)}' 폴더에 {files_in_current_target}개 파일 정리 완료.")
            processed_targets += 1
        
        final_message = f"총 {processed_targets}개 타겟 폴더 작업 완료. 총 {total_files_moved}개 파일 이동됨."
        self.update_status(final_message)
        messagebox.showinfo("작업 완료", final_message)

    def save_settings(self):
        filepath = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="설정 파일로 저장하기"
        )

        if not filepath:
            self.update_status("설정 저장이 취소되었습니다.")
            return

        settings = {
            'sources': self.sources,
            'targets': self.targets,
            'filename_option': self.filename_option.get(),
            'selection_mode': self.selection_mode_option.get()
        }
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(settings, f, ensure_ascii=False, indent=4)
            self.update_status(f"설정이 '{os.path.basename(filepath)}'에 저장되었습니다.")
        except Exception as e:
            messagebox.showerror("저장 실패", f"설정 저장 중 오류 발생: {e}")
            self.update_status(f"설정 저장 실패: {os.path.basename(filepath)}")

    def load_settings(self):
        filepath = filedialog.askopenfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="설정 파일 불러오기"
        )

        if not filepath:
            self.update_status("설정 불러오기가 취소되었습니다.")
            return
        
        # 설정 불러오기 전에 현재 UI와 내부 데이터 초기화
        self.sources.clear()
        self.source_tree.delete(*self.source_tree.get_children())
        self.targets.clear()
        self.target_listbox.delete(0, tk.END)
        self.source_path_entry.delete(0, tk.END)
        self.source_count_entry.delete(0, tk.END)
        self.target_path_entry.delete(0, tk.END)

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                settings = json.load(f)

            loaded_sources = settings.get('sources', [])
            for source_info in loaded_sources:
                if isinstance(source_info, dict) and 'path' in source_info and 'count' in source_info:
                    self.sources.append(source_info)
                    self.source_tree.insert("", tk.END, values=(source_info['path'], source_info['count']))
                else:
                    self.update_status(f"경고: 잘못된 소스 설정 항목({source_info})은 건너뜁니다.")

            loaded_targets = settings.get('targets', [])
            for target_path in loaded_targets:
                if isinstance(target_path, str):
                    self.targets.append(target_path)
                    self.target_listbox.insert(tk.END, target_path)
                else:
                    self.update_status(f"경고: 잘못된 타겟 설정 항목({target_path})은 건너뜁니다.")

            filename_option_loaded = settings.get('filename_option', "category_prefix")
            self.filename_option.set(filename_option_loaded)

            selection_mode_loaded = settings.get('selection_mode', 'sequential')
            self.selection_mode_option.set(selection_mode_loaded)

            self.update_status(f"'{os.path.basename(filepath)}'에서 설정을 불러왔습니다.")
        except json.JSONDecodeError:
            messagebox.showerror("불러오기 실패", f"설정 파일('{os.path.basename(filepath)}') 형식이 잘못되었거나 유효하지 않습니다.")
            self.update_status(f"설정 파일({os.path.basename(filepath)}) 형식 오류.")
        except Exception as e:
            messagebox.showerror("불러오기 실패", f"설정 불러오기 중 오류 발생: {e}")
            self.update_status(f"'{os.path.basename(filepath)}' 불러오기 실패.")

    # 타겟 폴더만 저장하는 새로운 메서드
    def save_targets_only(self):
        if not self.targets:
            messagebox.showwarning("저장 실패", "저장할 타겟 폴더가 없습니다.")
            return
            
        filepath = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="타겟 폴더 목록 저장",
            initialfile="타겟폴더목록.json"
        )

        if not filepath:
            self.update_status("타겟 폴더 저장이 취소되었습니다.")
            return

        target_data = {
            'targets': self.targets,
            'total_count': len(self.targets)
        }
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(target_data, f, ensure_ascii=False, indent=4)
            self.update_status(f"타겟 폴더 {len(self.targets)}개가 '{os.path.basename(filepath)}'에 저장되었습니다.")
            messagebox.showinfo("저장 완료", f"타겟 폴더 {len(self.targets)}개가 저장되었습니다.")
        except Exception as e:
            messagebox.showerror("저장 실패", f"타겟 폴더 저장 중 오류 발생: {e}")
            self.update_status(f"타겟 폴더 저장 실패: {os.path.basename(filepath)}")

    # 타겟 폴더만 불러오는 새로운 메서드
    def load_targets_only(self):
        filepath = filedialog.askopenfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="타겟 폴더 목록 불러오기"
        )

        if not filepath:
            self.update_status("타겟 폴더 불러오기가 취소되었습니다.")
            return
        
        # 기존 타겟 폴더 목록 비우기
        self.targets.clear()
        self.target_listbox.delete(0, tk.END)
        self.target_path_entry.delete(0, tk.END)

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                target_data = json.load(f)

            loaded_targets = target_data.get('targets', [])
            valid_count = 0
            
            for target_path in loaded_targets:
                if isinstance(target_path, str):
                    self.targets.append(target_path)
                    self.target_listbox.insert(tk.END, target_path)
                    valid_count += 1
                else:
                    self.update_status(f"경고: 잘못된 타겟 폴더 항목({target_path})은 건너뜁니다.")

            self.update_status(f"'{os.path.basename(filepath)}'에서 타겟 폴더 {valid_count}개를 불러왔습니다.")
            messagebox.showinfo("불러오기 완료", f"타겟 폴더 {valid_count}개를 불러왔습니다.")
            
        except json.JSONDecodeError:
            messagebox.showerror("불러오기 실패", f"타겟 폴더 파일('{os.path.basename(filepath)}') 형식이 잘못되었거나 유효하지 않습니다.")
            self.update_status(f"타겟 폴더 파일({os.path.basename(filepath)}) 형식 오류.")
        except Exception as e:
            messagebox.showerror("불러오기 실패", f"타겟 폴더 불러오기 중 오류 발생: {e}")
            self.update_status(f"'{os.path.basename(filepath)}' 불러오기 실패.")


if __name__ == "__main__":
    root = tk.Tk()
    app = PhotoOrganizerApp(root)
    root.mainloop()