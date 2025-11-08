import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import os
import subprocess
import threading
from pathlib import Path
import time
import json

class ImageToVideoConverter:
    def __init__(self, root):
        self.root = root
        self.root.title("이미지 → 동영상 변환기")
        self.root.geometry("900x900")
        self.root.resizable(True, True)
        
        # 변수 초기화
        self.source_folder = tk.StringVar()
        self.duration = tk.StringVar(value="1.0")
        self.fps = tk.StringVar(value="30")
        self.video_quality = tk.StringVar(value="high")
        self.is_processing = False
        self.total_folders = 0
        self.current_folder = 0
        self.folder_vars = {}  # 폴더별 체크박스 변수
        self.selected_folders = []  # 선택된 폴더 목록
        
        # 설정 파일 경로
        self.config_file = "converter_config.json"
        
        # GUI 구성
        self.setup_gui()
        
        # 이전 설정 불러오기
        self.load_config()
        
        # FFmpeg 확인
        self.check_ffmpeg()
    
    def setup_gui(self):
        # 메인 프레임
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 1. 폴더 선택 섹션
        folder_frame = ttk.LabelFrame(main_frame, text="폴더 설정", padding="10")
        folder_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        
        # 원본 폴더
        ttk.Label(folder_frame, text="원본 폴더:").grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Entry(folder_frame, textvariable=self.source_folder, width=50).grid(row=0, column=1, padx=5)
        ttk.Button(folder_frame, text="찾아보기", command=self.select_source_folder).grid(row=0, column=2)
        
        ttk.Label(folder_frame, text="※ 동영상은 각 폴더 내부에 생성됩니다").grid(row=1, column=1, sticky=tk.W, pady=5)
        
        # 2. 폴더 선택 섹션
        selection_frame = ttk.LabelFrame(main_frame, text="폴더 선택", padding="10")
        selection_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        
        # 버튼 프레임
        button_frame = ttk.Frame(selection_frame)
        button_frame.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        ttk.Button(button_frame, text="전체 선택", command=self.select_all_folders).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="전체 해제", command=self.deselect_all_folders).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="폴더 목록 새로고침", command=self.refresh_folder_list).pack(side=tk.LEFT, padx=5)
        
        self.selection_info = ttk.Label(button_frame, text="폴더를 선택해주세요")
        self.selection_info.pack(side=tk.RIGHT, padx=5)
        
        # 스크롤 가능한 폴더 리스트
        list_frame = ttk.Frame(selection_frame)
        list_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)
        
        # 스크롤바
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 캔버스 (스크롤 가능)
        self.canvas = tk.Canvas(list_frame, height=250, yscrollcommand=scrollbar.set)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.canvas.yview)
        
        # 폴더 리스트를 담을 프레임
        self.folders_frame = ttk.Frame(self.canvas)
        self.canvas_frame = self.canvas.create_window((0, 0), window=self.folders_frame, anchor="nw")
        
        # 캔버스 크기 조정 바인딩
        self.folders_frame.bind("<Configure>", self.on_frame_configure)
        
        # 3. 설정 섹션
        settings_frame = ttk.LabelFrame(main_frame, text="동영상 설정", padding="10")
        settings_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        
        # 이미지당 표시 시간
        ttk.Label(settings_frame, text="이미지당 표시 시간(초):").grid(row=0, column=0, sticky=tk.W, pady=5)
        duration_entry = ttk.Entry(settings_frame, textvariable=self.duration, width=10)
        duration_entry.grid(row=0, column=1, sticky=tk.W, padx=5)
        ttk.Label(settings_frame, text="(기본값: 1초)").grid(row=0, column=2, sticky=tk.W)
        
        # FPS
        ttk.Label(settings_frame, text="FPS (프레임/초):").grid(row=1, column=0, sticky=tk.W, pady=5)
        fps_combo = ttk.Combobox(settings_frame, textvariable=self.fps, width=10, 
                                values=["24", "25", "30", "60"])
        fps_combo.grid(row=1, column=1, sticky=tk.W, padx=5)
        ttk.Label(settings_frame, text="(기본값: 30)").grid(row=1, column=2, sticky=tk.W)
        
        # 품질
        ttk.Label(settings_frame, text="동영상 품질:").grid(row=2, column=0, sticky=tk.W, pady=5)
        quality_combo = ttk.Combobox(settings_frame, textvariable=self.video_quality, width=10,
                                    values=["low", "medium", "high", "very_high"])
        quality_combo.grid(row=2, column=1, sticky=tk.W, padx=5)
        ttk.Label(settings_frame, text="(기본값: high)").grid(row=2, column=2, sticky=tk.W)
        
        # 4. 진행률 섹션
        progress_frame = ttk.LabelFrame(main_frame, text="진행 상황", padding="10")
        progress_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        
        # 전체 진행률
        self.overall_label = ttk.Label(progress_frame, text="대기 중...")
        self.overall_label.grid(row=0, column=0, sticky=tk.W, pady=5)
        
        self.overall_progress = ttk.Progressbar(progress_frame, length=850, mode='determinate')
        self.overall_progress.grid(row=1, column=0, pady=5)
        
        # 현재 폴더 진행률
        self.current_label = ttk.Label(progress_frame, text="")
        self.current_label.grid(row=2, column=0, sticky=tk.W, pady=5)
        
        self.current_progress = ttk.Progressbar(progress_frame, length=850, mode='indeterminate')
        self.current_progress.grid(row=3, column=0, pady=5)
        
        # 6. 버튼 섹션 (로그 섹션 위에 배치)
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=4, column=0, columnspan=2, pady=10)
        
        self.start_button = ttk.Button(button_frame, text="변환 시작", command=self.start_conversion,
                                      style="Accent.TButton")
        self.start_button.grid(row=0, column=0, padx=5)
        
        self.stop_button = ttk.Button(button_frame, text="중지", command=self.stop_conversion,
                                     state=tk.DISABLED)
        self.stop_button.grid(row=0, column=1, padx=5)
        
        # 5. 로그 섹션
        log_frame = ttk.LabelFrame(main_frame, text="처리 로그", padding="10")
        log_frame.grid(row=5, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=4, width=105)
        self.log_text.grid(row=0, column=0)
        
        # 스타일 설정
        style = ttk.Style()
        style.configure("Accent.TButton", font=('Arial', 10, 'bold'))
    
    def check_ffmpeg(self):
        """FFmpeg 설치 확인"""
        try:
            subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
            self.log("✓ FFmpeg가 정상적으로 설치되어 있습니다.")
        except:
            self.log("✗ FFmpeg가 설치되어 있지 않습니다!")
            messagebox.showerror("FFmpeg 오류", 
                               "FFmpeg가 설치되어 있지 않습니다.\n"
                               "프로그램을 사용하려면 FFmpeg 설치가 필요합니다.")
    
    def select_source_folder(self):
        """원본 폴더 선택"""
        folder = filedialog.askdirectory(title="이미지가 들어있는 상위 폴더를 선택하세요")
        if folder:
            self.source_folder.set(folder)
            self.log(f"원본 폴더 선택: {folder}")
            # 폴더 목록 자동 새로고침
            self.refresh_folder_list()
    
    def refresh_folder_list(self):
        """폴더 목록 새로고침"""
        if not self.source_folder.get():
            messagebox.showwarning("경고", "먼저 원본 폴더를 선택해주세요.")
            return
        
        # 기존 체크박스 제거
        for widget in self.folders_frame.winfo_children():
            widget.destroy()
        self.folder_vars.clear()
        
        # 하위 폴더 스캔
        source = self.source_folder.get()
        subfolders = []
        
        try:
            for item in os.listdir(source):
                item_path = os.path.join(source, item)
                if os.path.isdir(item_path):
                    # 이미지 파일 개수 확인
                    image_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.gif']
                    image_count = sum(1 for f in os.listdir(item_path) 
                                    if any(f.lower().endswith(ext) for ext in image_extensions))
                    if image_count > 0:
                        subfolders.append((item, image_count))
            
            subfolders.sort(key=lambda x: x[0])  # 폴더명으로 정렬
            
            # 체크박스 생성
            for i, (folder_name, img_count) in enumerate(subfolders):
                var = tk.BooleanVar(value=True)  # 기본값: 선택됨
                self.folder_vars[folder_name] = var
                
                # 체크박스와 폴더 정보
                frame = ttk.Frame(self.folders_frame)
                frame.grid(row=i // 3, column=i % 3, sticky=(tk.W, tk.E), padx=10, pady=3)
                
                cb = ttk.Checkbutton(frame, text=f"{folder_name} ({img_count}장)", 
                                    variable=var, command=self.update_selection_info)
                cb.pack(side=tk.LEFT)
            
            self.log(f"발견된 폴더: {len(subfolders)}개")
            self.update_selection_info()
            
            # 캔버스 스크롤 영역 업데이트
            self.canvas.update_idletasks()
            self.canvas.config(scrollregion=self.canvas.bbox("all"))
            
        except Exception as e:
            messagebox.showerror("오류", f"폴더 목록을 읽는 중 오류 발생:\n{str(e)}")
    
    def on_frame_configure(self, event=None):
        """캔버스 스크롤 영역 업데이트"""
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
    
    def select_all_folders(self):
        """모든 폴더 선택"""
        for var in self.folder_vars.values():
            var.set(True)
        self.update_selection_info()
    
    def deselect_all_folders(self):
        """모든 폴더 선택 해제"""
        for var in self.folder_vars.values():
            var.set(False)
        self.update_selection_info()
    
    def update_selection_info(self):
        """선택 정보 업데이트"""
        total = len(self.folder_vars)
        selected = sum(1 for var in self.folder_vars.values() if var.get())
        self.selection_info.config(text=f"선택: {selected}/{total}개")
        
        # 선택된 폴더 목록 업데이트
        self.selected_folders = [name for name, var in self.folder_vars.items() if var.get()]
    
    def log(self, message):
        """로그 메시지 추가"""
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()
    
    def save_config(self):
        """설정 저장"""
        config = {
            "source_folder": self.source_folder.get(),
            "duration": self.duration.get(),
            "fps": self.fps.get(),
            "quality": self.video_quality.get()
        }
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except:
            pass
    
    def load_config(self):
        """설정 불러오기"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                self.source_folder.set(config.get("source_folder", ""))
                self.duration.set(config.get("duration", "1.0"))
                self.fps.set(config.get("fps", "30"))
                self.video_quality.set(config.get("quality", "high"))
        except:
            pass
    
    def get_quality_params(self):
        """품질에 따른 FFmpeg 파라미터 반환"""
        quality_map = {
            "low": "-crf 28 -preset fast",
            "medium": "-crf 23 -preset medium",
            "high": "-crf 18 -preset slow",
            "very_high": "-crf 15 -preset veryslow"
        }
        return quality_map.get(self.video_quality.get(), "-crf 18 -preset slow")
    
    def start_conversion(self):
        """변환 시작"""
        # 입력 확인
        if not self.source_folder.get():
            messagebox.showerror("오류", "원본 폴더를 선택해주세요.")
            return
        
        # 선택된 폴더 확인
        if not self.selected_folders:
            messagebox.showerror("오류", "변환할 폴더를 하나 이상 선택해주세요.")
            return
        
        # 설정 저장
        self.save_config()
        
        # 버튼 상태 변경
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.is_processing = True
        
        # 별도 스레드에서 실행
        thread = threading.Thread(target=self.process_folders)
        thread.daemon = True
        thread.start()
    
    def stop_conversion(self):
        """변환 중지"""
        self.is_processing = False
        self.log("사용자가 변환을 중지했습니다.")
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
    
    def process_folders(self):
        """폴더 처리 메인 함수"""
        source = self.source_folder.get()
        
        # 선택된 폴더만 처리
        folders_to_process = self.selected_folders.copy()
        
        self.total_folders = len(folders_to_process)
        self.current_folder = 0
        
        self.log(f"\n========== 변환 작업 시작 ==========")
        self.log(f"총 {self.total_folders}개 폴더를 처리합니다.")
        self.log(f"선택된 폴더: {', '.join(folders_to_process[:5])}" + 
                 (f" 외 {len(folders_to_process)-5}개" if len(folders_to_process) > 5 else ""))
        
        success_count = 0
        fail_count = 0
        
        for folder_name in folders_to_process:
            if not self.is_processing:
                break
            
            self.current_folder += 1
            folder_path = os.path.join(source, folder_name)
            
            # 진행률 업데이트
            self.overall_label.config(text=f"전체 진행률: {self.current_folder}/{self.total_folders} 폴더")
            self.overall_progress['value'] = (self.current_folder / self.total_folders) * 100
            
            # 현재 폴더 처리
            result = self.convert_folder_to_video(folder_path, folder_name)
            
            if result:
                success_count += 1
            else:
                fail_count += 1
        
        # 완료
        self.is_processing = False
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.current_progress.stop()
        
        if self.current_folder > 0:
            self.log(f"\n========== 변환 작업 완료 ==========")
            self.log(f"성공: {success_count}개, 실패: {fail_count}개")
            messagebox.showinfo("완료", f"변환이 완료되었습니다!\n성공: {success_count}개, 실패: {fail_count}개")
    
    def convert_folder_to_video(self, folder_path, folder_name):
        """개별 폴더를 동영상으로 변환"""
        self.current_label.config(text=f"처리 중: {folder_name}")
        self.current_progress.start()
        
        try:
            # 이미지 파일 찾기
            image_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.gif']
            images = []
            
            for file in os.listdir(folder_path):
                if any(file.lower().endswith(ext) for ext in image_extensions):
                    images.append(file)
            
            if not images:
                self.log(f"⚠ {folder_name}: 이미지 파일이 없습니다.")
                return False
            
            images.sort()  # 파일명 순서대로 정렬
            self.log(f"📁 {folder_name}: {len(images)}개 이미지 발견")
            
            # 첫 번째 이미지 정보 확인
            first_image_path = os.path.join(folder_path, images[0])
            self.log(f"  첫 번째 이미지: {images[0]}")
            
            # 출력 파일명 (원본 폴더에 저장)
            output_file = os.path.join(folder_path, f"{folder_name}.mp4")
            
            # 기존 파일이 있는지 확인
            if os.path.exists(output_file):
                self.log(f"  기존 파일 덮어쓰기: {folder_name}.mp4")
            
            # 출력 파일명 (원본 폴더에 저장)
            output_file = os.path.join(folder_path, f"{folder_name}.mp4")
            
            # 기존 파일이 있는지 확인
            if os.path.exists(output_file):
                self.log(f"  기존 파일 덮어쓰기: {folder_name}.mp4")
            
            # 임시 파일 리스트 생성 (원본 폴더에 생성)
            temp_file = os.path.join(folder_path, f"{folder_name}_filelist.txt")
            with open(temp_file, 'w', encoding='utf-8') as f:
                for img in images:
                    img_path = os.path.join(folder_path, img).replace('\\', '/')
                    f.write(f"file '{img_path}'\n")
                    f.write(f"duration {self.duration.get()}\n")
                # 마지막 이미지 추가 (FFmpeg 요구사항)
                if images:
                    last_img = os.path.join(folder_path, images[-1]).replace('\\', '/')
                    f.write(f"file '{last_img}'\n")
            
            # FFmpeg 명령어 구성
            quality_params = self.get_quality_params()
            cmd = [
                'ffmpeg',
                '-y',  # 기존 파일 덮어쓰기
                '-f', 'concat',
                '-safe', '0',
                '-i', temp_file,
                '-vf', f'scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps={self.fps.get()}',
                '-pix_fmt', 'yuv420p',  # 호환성을 위해
                *quality_params.split(),
                output_file
            ]
            
            # FFmpeg 실행
            process = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
            
            # 임시 파일 삭제
            try:
                os.remove(temp_file)
            except:
                pass
            
            if process.returncode == 0:
                self.log(f"✓ {folder_name}: 변환 완료! → {output_filename}")
                return True
            else:
                self.log(f"✗ {folder_name}: 변환 실패")
                error_msg = process.stderr if process.stderr else process.stdout
                if error_msg:
                    # 긴 오류 메시지는 주요 부분만 표시
                    error_lines = error_msg.strip().split('\n')
                    for line in error_lines[-5:]:  # 마지막 5줄만 표시
                        if line.strip():
                            self.log(f"  오류: {line.strip()}")
                else:
                    self.log(f"  오류: 알 수 없는 오류 (이미지 크기가 다르거나 파일명에 특수문자가 있을 수 있습니다)")
                return False
                
        except Exception as e:
            self.log(f"✗ {folder_name}: 오류 발생 - {str(e)}")
            return False
        finally:
            self.current_progress.stop()

def main():
    root = tk.Tk()
    app = ImageToVideoConverter(root)
    root.mainloop()

if __name__ == "__main__":
    main()