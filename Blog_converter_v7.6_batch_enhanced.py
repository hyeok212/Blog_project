"""
블로그 변환 프로그램 v7.6_batch_enhanced - 필수 항목 + 진정한 다중 업체 대량 변환
- v7.6의 필수 항목 기능 포함 (핵심 특징 보장)
- CSV 3컬럼 지원 (원본파일,키워드,프리셋파일)
- 여러 업체 동시 처리 가능
- 업체별 자동 폴더 분리
- 드래그앤드롭 기능
- 첫 번째 결과 미리보기
"""

import os
import csv
import json
import time
import logging
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk, simpledialog
from tkinter import font as tkfont
import threading
from queue import Queue
import traceback

# 드래그앤드롭 라이브러리 (선택사항)
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAS_DND = True
except ImportError:
    HAS_DND = False

# v7.6의 BlogConverter 클래스 임포트
import sys
import importlib.util
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 파일명에 점이 있어서 importlib 사용
spec = importlib.util.spec_from_file_location(
    "blog_converter_v76", 
    os.path.join(os.path.dirname(__file__), "Blog_converter_v7.6_smart_title.py")
)
blog_converter_v76 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(blog_converter_v76)

Config = blog_converter_v76.Config
StyleAnalysis = blog_converter_v76.StyleAnalysis
BusinessInfo = blog_converter_v76.BusinessInfo
BlogConverter = blog_converter_v76.BlogConverter
generate_short_name = blog_converter_v76.generate_short_name  # v7.6의 약칭 생성 함수


# ===== 고급 배치 처리 설정 =====
@dataclass
class EnhancedBatchConfig:
    """고급 배치 처리 설정"""
    output_base_dir: str = "output"
    preset_dir: str = "업체정보"
    csv_dir: str = "CSV파일"
    max_retries: int = 3
    retry_delay: int = 5
    api_delay: int = 2
    preview_first: bool = True
    batch_mode: bool = False
    auto_save_preset: bool = True


# ===== 고급 배치 작업 항목 =====
@dataclass
class EnhancedBatchItem:
    """고급 배치 처리 작업 항목"""
    index: int
    original_file: str
    seo_keyword: str
    business_name: str = ""
    preset_file: str = ""  # v7.6 신규: 업체별 프리셋 파일 경로
    status: str = "pending"
    result: Optional[str] = None
    error: Optional[str] = None
    retry_count: int = 0
    processing_time: float = 0.0
    generated_file_path: Optional[str] = None  # 생성된 파일 경로 추가


# ===== 업체 정보 관리자 =====
class BusinessInfoManager:
    """업체 정보 저장/불러오기 관리"""
    
    def __init__(self, preset_dir: str):
        self.preset_dir = preset_dir
        os.makedirs(preset_dir, exist_ok=True)
    
    def save_preset(self, business_info: BusinessInfo, filename: str = None) -> str:
        """업체 정보를 JSON으로 저장"""
        if not filename:
            filename = f"{business_info.name}.json"
        
        filepath = os.path.join(self.preset_dir, filename)
        
        # BusinessInfo를 딕셔너리로 변환
        data = {
            'name': business_info.name,
            'short_name': business_info.short_name,  # v7.5 추가
            'address': business_info.address,
            'hours': business_info.hours,
            'phone': business_info.phone,
            'features': business_info.features,
            'menu_items': business_info.menu_items,
            'ordered_items': business_info.ordered_items,
            'atmosphere': business_info.atmosphere,
            'target_customer': business_info.target_customer,
            'parking_info': business_info.parking_info
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return filepath
    
    def load_preset(self, filename: str) -> BusinessInfo:
        """JSON에서 업체 정보 불러오기"""
        filepath = os.path.join(self.preset_dir, filename)
        
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # BusinessInfo 객체로 변환
        business_info = BusinessInfo()
        business_info.name = data.get('name', '')
        business_info.short_name = data.get('short_name', '')  # v7.5 추가
        business_info.address = data.get('address', '')
        business_info.hours = data.get('hours', '')
        business_info.phone = data.get('phone', '')
        business_info.features = data.get('features', [])
        business_info.menu_items = data.get('menu_items', [])
        business_info.ordered_items = data.get('ordered_items', [])
        business_info.atmosphere = data.get('atmosphere', '')
        business_info.target_customer = data.get('target_customer', '')
        business_info.parking_info = data.get('parking_info', '')
        
        # 약칭이 없으면 자동 생성 (v7.5)
        if not business_info.short_name and business_info.name:
            business_info.short_name = generate_short_name(business_info.name)
        
        return business_info
    
    def list_presets(self) -> List[str]:
        """저장된 프리셋 목록 반환"""
        files = []
        for filename in os.listdir(self.preset_dir):
            if filename.endswith('.json'):
                files.append(filename)
        return sorted(files)


# ===== CSV 파서 =====
class CSVParser:
    """CSV 파일 파싱"""
    
    @staticmethod
    def parse_enhanced_csv(filepath: str) -> List[EnhancedBatchItem]:
        """v7.6: CSV 파싱 (파일경로, 키워드, 프리셋파일)"""
        items = []
        
        try:
            # BOM 처리
            with open(filepath, 'rb') as f:
                raw = f.read()
                if raw.startswith(b'\xef\xbb\xbf'):
                    raw = raw[3:]
                content = raw.decode('utf-8')
            
            # CSV 파싱
            reader = csv.DictReader(content.splitlines())
            
            for idx, row in enumerate(reader):
                # 필수 필드
                original_file = row.get('원본파일경로', '').strip()
                seo_keyword = row.get('키워드', '').strip()
                
                if not original_file or not seo_keyword:
                    continue
                
                # 파일 존재 확인
                if not os.path.exists(original_file):
                    print(f"경고: 파일이 존재하지 않음 - {original_file}")
                    continue
                
                # v7.6: 프리셋 파일 (선택적)
                preset_file = row.get('프리셋파일', '').strip()
                
                item = EnhancedBatchItem(
                    index=idx,
                    original_file=original_file,
                    seo_keyword=seo_keyword,
                    preset_file=preset_file  # v7.6 신규
                )
                
                items.append(item)
        
        except Exception as e:
            raise Exception(f"CSV 파일 파싱 오류: {str(e)}")
        
        return items


# ===== 고급 배치 처리기 =====
class EnhancedBatchProcessor:
    """고급 대량 변환 처리"""
    
    def __init__(self, config: Config, batch_config: EnhancedBatchConfig):
        self.config = config
        self.batch_config = batch_config
        self.converter = BlogConverter(config)
        self.business_info_manager = BusinessInfoManager(batch_config.preset_dir)
        self.items: List[EnhancedBatchItem] = []
        self.current_business_info: Optional[BusinessInfo] = None
        self.stop_flag = False
        self.pause_flag = False
        
        # 로깅 설정
        self.setup_logging()
    
    def setup_logging(self):
        """로깅 설정"""
        log_dir = os.path.join(self.batch_config.output_base_dir, "로그")
        os.makedirs(log_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = os.path.join(log_dir, f"batch_{timestamp}.log")
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def load_csv(self, csv_path: str):
        """CSV 파일 로드"""
        self.items = CSVParser.parse_enhanced_csv(csv_path)
        self.logger.info(f"CSV 파일 로드 완료: {len(self.items)}개 항목")
    
    def set_business_info(self, business_info: BusinessInfo):
        """업체 정보 설정"""
        self.current_business_info = business_info
        # 모든 항목에 업체명 설정
        for item in self.items:
            item.business_name = business_info.name
    
    def process_all(self, progress_callback=None, status_callback=None):
        """v7.6: 전체 처리 (다중 업체 지원)"""
        if not self.items:
            raise ValueError("처리할 항목이 없습니다.")
        
        # v7.6: 업체별 정보 캐시 (동일 프리셋 반복 로드 방지)
        business_info_cache = {}
        
        # v7.6: 첫 번째 항목에서 업체 정보 확인
        first_item = self.items[0]
        if first_item.preset_file:
            # CSV에 프리셋 파일이 지정된 경우
            try:
                default_business_info = self.business_info_manager.load_preset(first_item.preset_file)
            except:
                # 프리셋 로드 실패시 GUI에서 설정한 정보 사용
                if not self.current_business_info:
                    raise ValueError("업체 정보가 설정되지 않았습니다.")
                default_business_info = self.current_business_info
        else:
            # 프리셋 파일이 없으면 GUI에서 설정한 정보 사용
            if not self.current_business_info:
                raise ValueError("업체 정보가 설정되지 않았습니다.")
            default_business_info = self.current_business_info
        
        # 타임스탬프 생성
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        total_items = len(self.items)
        processed = 0
        success_count = 0
        failed_items = []
        
        # v7.6: 업체별 결과 저장을 위한 디렉토리 맵
        output_dirs = {}
        
        self.logger.info(f"처리 시작: 총 {total_items}개 항목")
        
        for item in self.items:
            if self.stop_flag:
                self.logger.info("사용자에 의해 중지됨")
                break
            
            while self.pause_flag:
                time.sleep(0.5)
            
            try:
                # 원본 파일 읽기
                with open(item.original_file, 'r', encoding='utf-8') as f:
                    original_text = f.read()
                
                # v7.6: 이 항목의 업체 정보 결정
                if item.preset_file:
                    # 캐시 확인
                    if item.preset_file not in business_info_cache:
                        try:
                            business_info_cache[item.preset_file] = self.business_info_manager.load_preset(item.preset_file)
                        except Exception as e:
                            self.logger.warning(f"프리셋 로드 실패 ({item.preset_file}): {str(e)}")
                            business_info_cache[item.preset_file] = default_business_info
                    
                    current_business_info = business_info_cache[item.preset_file]
                else:
                    current_business_info = default_business_info
                
                # v7.6: 업체별 출력 디렉토리 생성
                business_name = current_business_info.name
                if business_name not in output_dirs:
                    output_dir = os.path.join(
                        self.batch_config.output_base_dir,
                        f"{business_name}_{timestamp}",
                        "성공"
                    )
                    os.makedirs(output_dir, exist_ok=True)
                    
                    failed_dir = os.path.join(
                        self.batch_config.output_base_dir,
                        f"{business_name}_{timestamp}",
                        "실패"
                    )
                    os.makedirs(failed_dir, exist_ok=True)
                    
                    output_dirs[business_name] = {
                        'success': output_dir,
                        'failed': failed_dir
                    }
                
                # SEO 키워드 업데이트
                temp_business_info = BusinessInfo()
                # 모든 필드 복사
                for key, value in current_business_info.__dict__.items():
                    setattr(temp_business_info, key, value)
                # 이 항목의 키워드로 교체
                temp_business_info.seo_keywords = [item.seo_keyword]
                
                # 변환 시작
                start_time = time.time()
                item.status = "processing"
                
                if status_callback:
                    status_callback(item.index, "processing", f"변환 중...")
                
                # 변환 수행
                result = self.converter.convert(original_text, temp_business_info)
                
                if result['success']:
                    item.result = result['result']
                    item.status = "success"
                    item.processing_time = time.time() - start_time
                    
                    # v7.6: 업체별 디렉토리에 파일 저장
                    filename = f"{business_name}_{item.seo_keyword}.txt"
                    filepath = os.path.join(output_dirs[business_name]['success'], filename)
                    
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(item.result)
                    
                    item.generated_file_path = filepath
                    success_count += 1
                    
                    if status_callback:
                        status_callback(item.index, "success", f"완료 ({item.processing_time:.1f}초)")
                    
                    self.logger.info(f"성공: {filename}")
                else:
                    raise Exception(result.get('error', '알 수 없는 오류'))
            
            except Exception as e:
                item.error = str(e)
                item.status = "failed"
                item.retry_count += 1
                
                # 재시도
                if item.retry_count < self.batch_config.max_retries:
                    self.logger.warning(f"재시도 {item.retry_count}/{self.batch_config.max_retries}: {item.seo_keyword}")
                    time.sleep(self.batch_config.retry_delay)
                    continue
                
                failed_items.append(item)
                
                if status_callback:
                    status_callback(item.index, "failed", str(e)[:50])
                
                self.logger.error(f"실패: {item.seo_keyword} - {str(e)}")
            
            processed += 1
            
            if progress_callback:
                progress_callback(processed, total_items)
            
            # API 호출 간격
            if processed < total_items:
                time.sleep(self.batch_config.api_delay)
        
        # v7.6: 업체별 실패 항목 정리
        business_failed_items = {}
        for item in failed_items:
            # 이 항목의 업체 결정
            if item.preset_file and item.preset_file in business_info_cache:
                business_name = business_info_cache[item.preset_file].name
            else:
                business_name = default_business_info.name
            
            if business_name not in business_failed_items:
                business_failed_items[business_name] = []
            business_failed_items[business_name].append(item)
        
        # v7.6: 업체별 실패 항목 CSV 저장
        for business_name, items in business_failed_items.items():
            if business_name in output_dirs:
                self._save_failed_items(items, output_dirs[business_name]['failed'])
        
        # v7.6: 업체별 요약 저장
        all_summaries = {}
        for business_name, dirs in output_dirs.items():
            # 이 업체의 항목 수 계산
            business_items = [item for item in self.items 
                            if (item.preset_file and business_name == business_info_cache.get(item.preset_file, default_business_info).name)
                            or (not item.preset_file and business_name == default_business_info.name)]
            
            business_success = len([item for item in business_items if item.status == "success"])
            business_failed = len([item for item in business_items if item.status == "failed"])
            
            summary = {
                'total': len(business_items),
                'success': business_success,
                'failed': business_failed,
                'business_name': business_name,
                'timestamp': timestamp
            }
            
            summary_path = os.path.join(
                os.path.dirname(dirs['success']),
                "summary.json"
            )
            
            with open(summary_path, 'w', encoding='utf-8') as f:
                json.dump(summary, f, ensure_ascii=False, indent=2)
            
            all_summaries[business_name] = summary
        
        # CSV 파일 업데이트 (생성된 파일 경로 추가)
        self._update_csv_with_paths()
        
        self.logger.info(f"처리 완료: 성공 {success_count}/{total_items}")
        
        # v7.6: 전체 요약 반환
        return {
            'total': total_items,
            'success': success_count,
            'failed': len(failed_items),
            'by_business': all_summaries,
            'timestamp': timestamp
        }
    
    def _save_failed_items(self, failed_items: List[EnhancedBatchItem], failed_dir: str):
        """v7.6: 실패 항목 CSV 저장 (프리셋 파일 포함)"""
        csv_path = os.path.join(failed_dir, "failed_items.csv")
        
        with open(csv_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['원본파일경로', '키워드', '프리셋파일', '에러메시지'])
            
            for item in failed_items:
                writer.writerow([
                    item.original_file,
                    item.seo_keyword,
                    item.preset_file if item.preset_file else '',
                    item.error
                ])
    
    def _update_csv_with_paths(self):
        """원본 CSV에 생성된 파일 경로 추가"""
        # 구현 예정 (필요시)
        pass
    
    def stop(self):
        """처리 중지"""
        self.stop_flag = True
    
    def pause(self):
        """일시 정지"""
        self.pause_flag = True
    
    def resume(self):
        """재개"""
        self.pause_flag = False


# ===== GUI 인터페이스 =====
class EnhancedBatchGUI:
    """고급 배치 처리 GUI"""
    
    def __init__(self):
        # DnD 지원 여부에 따라 윈도우 생성
        if HAS_DND:
            self.root = TkinterDnD.Tk()
        else:
            self.root = tk.Tk()
        
        self.root.title("블로그 변환 프로그램 v7.6 Batch Enhanced - 필수 항목 + 다중 업체 처리")
        self.root.geometry("1200x800")
        
        # 설정
        self.config = Config()
        self.batch_config = EnhancedBatchConfig()
        self.processor = None
        self.business_info = BusinessInfo()
        self.processing_thread = None
        
        # GUI 컴포넌트
        self.csv_path_var = tk.StringVar()
        self.items_tree = None
        self.progress_var = tk.DoubleVar()
        self.status_var = tk.StringVar(value="대기 중")
        
        self.setup_ui()
        self.load_config()
    
    def setup_ui(self):
        """UI 구성"""
        # 노트북 (탭) 생성
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 탭들
        self.setup_api_tab(notebook)
        self.setup_business_tab(notebook)
        self.setup_csv_tab(notebook)
        self.setup_options_tab(notebook)
        self.setup_progress_tab(notebook)
        
        # 하단 컨트롤
        self.setup_controls()
    
    def setup_api_tab(self, notebook):
        """API 설정 탭"""
        api_frame = ttk.Frame(notebook)
        notebook.add(api_frame, text="API 설정")
        
        # API 키 입력
        ttk.Label(api_frame, text="OpenAI API Key:", font=('맑은 고딕', 10)).grid(row=0, column=0, sticky=tk.W, padx=20, pady=20)
        
        self.api_key_var = tk.StringVar()
        api_entry = ttk.Entry(api_frame, textvariable=self.api_key_var, width=50, show="*")
        api_entry.grid(row=0, column=1, padx=10, pady=20)
        
        ttk.Button(api_frame, text="저장", command=self.save_api_key).grid(row=0, column=2, padx=10)
        
        # API 사용량 예측
        usage_frame = ttk.LabelFrame(api_frame, text="예상 API 사용량", padding=20)
        usage_frame.grid(row=1, column=0, columnspan=3, padx=20, pady=20, sticky=(tk.W, tk.E))
        
        self.usage_label = ttk.Label(usage_frame, text="CSV 파일을 로드하면 예상 비용이 표시됩니다.")
        self.usage_label.pack()
    
    def setup_business_tab(self, notebook):
        """업체 정보 탭"""
        business_frame = ttk.Frame(notebook)
        notebook.add(business_frame, text="업체 정보")
        
        # 스크롤 가능한 프레임
        canvas = tk.Canvas(business_frame)
        scrollbar = ttk.Scrollbar(business_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # 프리셋 관리
        preset_frame = ttk.LabelFrame(scrollable_frame, text="업체 정보 프리셋", padding=10)
        preset_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), padx=20, pady=10)
        
        ttk.Button(preset_frame, text="프리셋 불러오기", command=self.load_preset).pack(side=tk.LEFT, padx=5)
        ttk.Button(preset_frame, text="프리셋 저장", command=self.save_preset).pack(side=tk.LEFT, padx=5)
        ttk.Button(preset_frame, text="프리셋 관리", command=self.manage_presets).pack(side=tk.LEFT, padx=5)
        
        # 업체 정보 입력 필드들
        row = 1
        
        # 업체명
        ttk.Label(scrollable_frame, text="업체명*:").grid(row=row, column=0, sticky=tk.W, padx=20, pady=5)
        self.name_var = tk.StringVar()
        name_entry = ttk.Entry(scrollable_frame, textvariable=self.name_var, width=40)
        name_entry.grid(row=row, column=1, pady=5)
        name_entry.bind('<FocusOut>', self.on_name_change)
        row += 1
        
        # 제목용 약칭 (v7.5)
        ttk.Label(scrollable_frame, text="제목용 약칭:").grid(row=row, column=0, sticky=tk.W, padx=20, pady=5)
        self.short_name_var = tk.StringVar()
        short_entry = ttk.Entry(scrollable_frame, textvariable=self.short_name_var, width=40)
        short_entry.grid(row=row, column=1, pady=5)
        ttk.Label(scrollable_frame, text="(자동생성됨, 수정가능)", font=('맑은 고딕', 8)).grid(row=row, column=2, sticky=tk.W, padx=5)
        row += 1
        
        # 주소
        ttk.Label(scrollable_frame, text="주소*:").grid(row=row, column=0, sticky=tk.W, padx=20, pady=5)
        self.address_var = tk.StringVar()
        ttk.Entry(scrollable_frame, textvariable=self.address_var, width=40).grid(row=row, column=1, pady=5)
        row += 1
        
        # 운영시간
        ttk.Label(scrollable_frame, text="운영시간:").grid(row=row, column=0, sticky=tk.W, padx=20, pady=5)
        self.hours_var = tk.StringVar()
        ttk.Entry(scrollable_frame, textvariable=self.hours_var, width=40).grid(row=row, column=1, pady=5)
        row += 1
        
        # 전화번호
        ttk.Label(scrollable_frame, text="전화번호:").grid(row=row, column=0, sticky=tk.W, padx=20, pady=5)
        self.phone_var = tk.StringVar()
        ttk.Entry(scrollable_frame, textvariable=self.phone_var, width=40).grid(row=row, column=1, pady=5)
        row += 1
        
        # 전체 메뉴
        ttk.Label(scrollable_frame, text="전체 메뉴*\n(형식: 메뉴명:가격):").grid(row=row, column=0, sticky=tk.W, padx=20, pady=5)
        self.menu_text = tk.Text(scrollable_frame, width=40, height=4)
        self.menu_text.grid(row=row, column=1, pady=5)
        row += 1
        
        # 식사 메뉴
        ttk.Label(scrollable_frame, text="식사 메뉴*\n(실제 주문한 메뉴):").grid(row=row, column=0, sticky=tk.W, padx=20, pady=5)
        self.ordered_menu_text = tk.Text(scrollable_frame, width=40, height=4)
        self.ordered_menu_text.grid(row=row, column=1, pady=5)
        row += 1
        
        # 주요 특징
        ttk.Label(scrollable_frame, text="주요 특징*\n(줄바꿈구분):").grid(row=row, column=0, sticky=tk.W, padx=20, pady=5)
        
        # v7.6: 특징 입력 프레임 (도움말 포함)
        features_frame = ttk.Frame(scrollable_frame)
        features_frame.grid(row=row, column=1, pady=5, sticky=(tk.W, tk.E))
        
        self.features_text = tk.Text(features_frame, width=40, height=4)
        self.features_text.pack(side=tk.TOP)
        
        # 도움말 텍스트
        help_text = ("💡 v7.6 특징 작성 가이드:\n"
                    "• 15-25개 작성 권장 (다양성 확보)\n" 
                    "• [필수] 표시: 항상 포함될 핵심 특징\n"
                    "  예) [필수] 14시간 우려낸 사골 육수\n"
                    "• 나머지는 랜덤 선택 (총 7-8개 사용)")
        
        help_label = ttk.Label(features_frame, text=help_text, 
                              font=("맑은 고딕", 8), foreground="gray")
        help_label.pack(side=tk.TOP, anchor=tk.W, pady=(2, 0))
        
        row += 1
        
        # 분위기
        ttk.Label(scrollable_frame, text="분위기:").grid(row=row, column=0, sticky=tk.W, padx=20, pady=5)
        self.atmosphere_var = tk.StringVar()
        ttk.Entry(scrollable_frame, textvariable=self.atmosphere_var, width=40).grid(row=row, column=1, pady=5)
        row += 1
        
        # 타겟 고객
        ttk.Label(scrollable_frame, text="타겟 고객:").grid(row=row, column=0, sticky=tk.W, padx=20, pady=5)
        self.target_customer_var = tk.StringVar()
        ttk.Entry(scrollable_frame, textvariable=self.target_customer_var, width=40).grid(row=row, column=1, pady=5)
        row += 1
        
        # 주차 정보
        ttk.Label(scrollable_frame, text="주차 정보:").grid(row=row, column=0, sticky=tk.W, padx=20, pady=5)
        self.parking_text = tk.Text(scrollable_frame, width=40, height=2)
        self.parking_text.grid(row=row, column=1, pady=5)
        
        # 캔버스와 스크롤바 배치
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def setup_csv_tab(self, notebook):
        """CSV 관리 탭"""
        csv_frame = ttk.Frame(notebook)
        notebook.add(csv_frame, text="CSV 관리")
        
        # CSV 파일 선택
        file_frame = ttk.LabelFrame(csv_frame, text="CSV 파일", padding=20)
        file_frame.pack(fill=tk.X, padx=20, pady=20)
        
        self.csv_label = ttk.Label(file_frame, text="CSV 파일을 선택하거나 드래그앤드롭하세요")
        self.csv_label.pack(pady=10)
        
        ttk.Button(file_frame, text="CSV 파일 선택", command=self.select_csv).pack(pady=5)
        
        # v7.6: CSV 형식 안내
        format_text = ("📌 v7.6 CSV 형식 (3컬럼 지원):\n"
                      "원본파일경로,키워드,프리셋파일\n"
                      "blog1.txt,일산 칼국수 맛집,프리셋/업체정보/대종칼국수.json\n"
                      "blog2.txt,강남 파스타 맛집,프리셋/업체정보/올리브가든.json\n"
                      "※ 프리셋파일 비우면 GUI 설정 사용")
        
        format_label = ttk.Label(file_frame, text=format_text, 
                               font=("맑은 고딕", 8), foreground="gray")
        format_label.pack(pady=(10, 0))
        
        # 드래그앤드롭 설정
        if HAS_DND:
            file_frame.drop_target_register(DND_FILES)
            file_frame.dnd_bind('<<Drop>>', self.drop_csv)
        
        # CSV 내용 표시
        content_frame = ttk.LabelFrame(csv_frame, text="CSV 내용", padding=10)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # 트리뷰
        columns = ('번호', '원본파일', '키워드', '프리셋', '상태')  # v7.6: 프리셋 컬럼 추가
        self.items_tree = ttk.Treeview(content_frame, columns=columns, show='headings', height=15)
        
        for col in columns:
            self.items_tree.heading(col, text=col)
            if col == '원본파일':
                self.items_tree.column(col, width=200)
            elif col == '프리셋':
                self.items_tree.column(col, width=150)
            else:
                self.items_tree.column(col, width=120)
        
        # 스크롤바
        vsb = ttk.Scrollbar(content_frame, orient="vertical", command=self.items_tree.yview)
        self.items_tree.configure(yscrollcommand=vsb.set)
        
        self.items_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        
        # CSV 정보
        self.csv_info_label = ttk.Label(csv_frame, text="")
        self.csv_info_label.pack(pady=10)
    
    def setup_options_tab(self, notebook):
        """실행 옵션 탭"""
        options_frame = ttk.Frame(notebook)
        notebook.add(options_frame, text="실행 옵션")
        
        # 처리 옵션
        process_frame = ttk.LabelFrame(options_frame, text="처리 옵션", padding=20)
        process_frame.pack(fill=tk.X, padx=20, pady=20)
        
        self.preview_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(process_frame, text="첫 번째 결과 미리보기", 
                       variable=self.preview_var).pack(anchor=tk.W, pady=5)
        
        self.batch_mode_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(process_frame, text="배치 모드 (여러 업체 연속 처리)", 
                       variable=self.batch_mode_var).pack(anchor=tk.W, pady=5)
        
        # 재시도 설정
        retry_frame = ttk.LabelFrame(options_frame, text="재시도 설정", padding=20)
        retry_frame.pack(fill=tk.X, padx=20, pady=10)
        
        ttk.Label(retry_frame, text="최대 재시도 횟수:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.retry_var = tk.IntVar(value=3)
        ttk.Spinbox(retry_frame, from_=0, to=5, textvariable=self.retry_var, width=10).grid(row=0, column=1, pady=5)
        
        ttk.Label(retry_frame, text="API 호출 간격(초):").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.delay_var = tk.IntVar(value=2)
        ttk.Spinbox(retry_frame, from_=1, to=10, textvariable=self.delay_var, width=10).grid(row=1, column=1, pady=5)
        
        # 출력 설정
        output_frame = ttk.LabelFrame(options_frame, text="출력 설정", padding=20)
        output_frame.pack(fill=tk.X, padx=20, pady=10)
        
        ttk.Label(output_frame, text="출력 디렉토리:").pack(anchor=tk.W)
        self.output_var = tk.StringVar(value="output")
        ttk.Entry(output_frame, textvariable=self.output_var, width=50).pack(fill=tk.X, pady=5)
        ttk.Button(output_frame, text="찾아보기", command=self.select_output_dir).pack(pady=5)
    
    def setup_progress_tab(self, notebook):
        """진행 상황 탭"""
        progress_frame = ttk.Frame(notebook)
        notebook.add(progress_frame, text="진행 상황")
        
        # 전체 진행률
        overall_frame = ttk.LabelFrame(progress_frame, text="전체 진행률", padding=20)
        overall_frame.pack(fill=tk.X, padx=20, pady=20)
        
        self.progress_bar = ttk.Progressbar(overall_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, pady=10)
        
        self.progress_label = ttk.Label(overall_frame, text="0 / 0")
        self.progress_label.pack()
        
        # 실시간 로그
        log_frame = ttk.LabelFrame(progress_frame, text="실시간 로그", padding=10)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=20, wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        # 통계
        stats_frame = ttk.LabelFrame(progress_frame, text="통계", padding=20)
        stats_frame.pack(fill=tk.X, padx=20, pady=10)
        
        self.stats_label = ttk.Label(stats_frame, text="대기 중...")
        self.stats_label.pack()
    
    def setup_controls(self):
        """하단 컨트롤"""
        control_frame = ttk.Frame(self.root)
        control_frame.pack(fill=tk.X, padx=20, pady=10)
        
        # 상태 표시
        self.status_label = ttk.Label(control_frame, textvariable=self.status_var, 
                                     font=('맑은 고딕', 10, 'bold'))
        self.status_label.pack(side=tk.LEFT, padx=10)
        
        # 버튼들
        self.start_btn = ttk.Button(control_frame, text="변환 시작", 
                                   command=self.start_processing, style="Accent.TButton")
        self.start_btn.pack(side=tk.RIGHT, padx=5)
        
        self.stop_btn = ttk.Button(control_frame, text="중지", 
                                  command=self.stop_processing, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.RIGHT, padx=5)
        
        self.pause_btn = ttk.Button(control_frame, text="일시정지", 
                                   command=self.toggle_pause, state=tk.DISABLED)
        self.pause_btn.pack(side=tk.RIGHT, padx=5)
        
        # 스타일 설정
        style = ttk.Style()
        style.configure("Accent.TButton", foreground="blue")
    
    def on_name_change(self, event):
        """업체명 변경시 약칭 자동 생성 (v7.5)"""
        full_name = self.name_var.get().strip()
        if full_name and not self.short_name_var.get():
            short_name = generate_short_name(full_name)
            self.short_name_var.set(short_name)
    
    def load_config(self):
        """설정 로드"""
        config_file = "blog_converter_config.json"
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.config.API_KEY = data.get('api_key', '')
                    self.api_key_var.set(self.config.API_KEY)
                    self.log_message("설정을 로드했습니다.")
            except:
                pass
    
    def save_api_key(self):
        """API 키 저장"""
        self.config.API_KEY = self.api_key_var.get()
        
        config_data = {'api_key': self.config.API_KEY}
        with open("blog_converter_config.json", 'w', encoding='utf-8') as f:
            json.dump(config_data, f)
        
        messagebox.showinfo("저장 완료", "API 키가 저장되었습니다.")
        self.log_message("API 키가 저장되었습니다.")
    
    def select_csv(self):
        """CSV 파일 선택"""
        filename = filedialog.askopenfilename(
            title="CSV 파일 선택",
            filetypes=[("CSV 파일", "*.csv"), ("모든 파일", "*.*")]
        )
        
        if filename:
            self.load_csv_file(filename)
    
    def drop_csv(self, event):
        """CSV 파일 드롭"""
        files = self.root.tk.splitlist(event.data)
        if files and files[0].endswith('.csv'):
            self.load_csv_file(files[0])
    
    def load_csv_file(self, filepath):
        """CSV 파일 로드"""
        try:
            self.csv_path_var.set(filepath)
            
            # 프로세서 초기화
            if not self.processor:
                self.processor = EnhancedBatchProcessor(self.config, self.batch_config)
            
            # CSV 로드
            self.processor.load_csv(filepath)
            
            # 트리뷰 업데이트
            self.update_tree_view()
            
            # 정보 업데이트
            self.csv_label.config(text=os.path.basename(filepath))
            self.csv_info_label.config(text=f"총 {len(self.processor.items)}개 항목")
            
            # 예상 비용 계산
            self.update_usage_estimate()
            
            self.log_message(f"CSV 파일 로드: {len(self.processor.items)}개 항목")
            
        except Exception as e:
            messagebox.showerror("오류", f"CSV 파일 로드 실패: {str(e)}")
            self.log_message(f"CSV 로드 오류: {str(e)}")
    
    def update_tree_view(self):
        """v7.6: 트리뷰 업데이트 (프리셋 표시)"""
        # 기존 항목 삭제
        for item in self.items_tree.get_children():
            self.items_tree.delete(item)
        
        # 새 항목 추가
        for batch_item in self.processor.items:
            # 프리셋 파일명만 표시 (경로 제외)
            preset_display = os.path.basename(batch_item.preset_file) if batch_item.preset_file else "GUI 설정"
            
            self.items_tree.insert('', 'end', values=(
                batch_item.index + 1,
                os.path.basename(batch_item.original_file),
                batch_item.seo_keyword,
                preset_display,
                batch_item.status
            ))
    
    def update_usage_estimate(self):
        """API 사용량 예측"""
        if self.processor and self.processor.items:
            item_count = len(self.processor.items)
            # 예상 토큰 (변환 + 제목 생성)
            est_tokens = item_count * 3500  # 변환 3000 + 제목 500
            est_cost = est_tokens * 0.00002  # 대략적인 가격
            
            self.usage_label.config(
                text=f"예상 사용량: {item_count}개 항목 × 3,500 토큰 = {est_tokens:,} 토큰\n"
                     f"예상 비용: ${est_cost:.2f} (약 {int(est_cost * 1300):,}원)"
            )
    
    def load_preset(self):
        """프리셋 불러오기"""
        manager = BusinessInfoManager(self.batch_config.preset_dir)
        presets = manager.list_presets()
        
        if not presets:
            messagebox.showinfo("알림", "저장된 프리셋이 없습니다.")
            return
        
        # 선택 대화상자
        dialog = tk.Toplevel(self.root)
        dialog.title("프리셋 선택")
        dialog.geometry("400x300")
        
        ttk.Label(dialog, text="불러올 프리셋을 선택하세요:").pack(pady=10)
        
        listbox = tk.Listbox(dialog, height=10)
        listbox.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        for preset in presets:
            listbox.insert(tk.END, preset)
        
        def on_select():
            selection = listbox.curselection()
            if selection:
                preset_name = listbox.get(selection[0])
                try:
                    business_info = manager.load_preset(preset_name)
                    self.load_business_info(business_info)
                    dialog.destroy()
                    messagebox.showinfo("성공", f"프리셋 '{preset_name}'을 불러왔습니다.")
                except Exception as e:
                    messagebox.showerror("오류", f"프리셋 로드 실패: {str(e)}")
        
        ttk.Button(dialog, text="선택", command=on_select).pack(pady=10)
    
    def save_preset(self):
        """프리셋 저장"""
        if not self.get_business_info():
            return
        
        # 파일명 입력
        filename = simpledialog.askstring("프리셋 저장", "프리셋 이름을 입력하세요:")
        if not filename:
            return
        
        if not filename.endswith('.json'):
            filename += '.json'
        
        try:
            manager = BusinessInfoManager(self.batch_config.preset_dir)
            filepath = manager.save_preset(self.business_info, filename)
            messagebox.showinfo("성공", f"프리셋이 저장되었습니다:\n{filepath}")
            self.log_message(f"프리셋 저장: {filename}")
        except Exception as e:
            messagebox.showerror("오류", f"프리셋 저장 실패: {str(e)}")
    
    def manage_presets(self):
        """프리셋 관리"""
        import subprocess
        preset_dir = os.path.abspath(self.batch_config.preset_dir)
        
        if os.name == 'nt':  # Windows
            os.startfile(preset_dir)
        else:  # macOS, Linux
            subprocess.run(['open', preset_dir])
    
    def load_business_info(self, business_info: BusinessInfo):
        """업체 정보를 GUI에 로드"""
        self.name_var.set(business_info.name)
        self.short_name_var.set(business_info.short_name)  # v7.5
        self.address_var.set(business_info.address)
        self.hours_var.set(business_info.hours)
        self.phone_var.set(business_info.phone)
        self.atmosphere_var.set(business_info.atmosphere)
        self.target_customer_var.set(business_info.target_customer)
        
        # 메뉴
        self.menu_text.delete(1.0, tk.END)
        for menu in business_info.menu_items:
            line = f"{menu['name']}:{menu['price']}" if menu.get('price') else menu['name']
            self.menu_text.insert(tk.END, line + '\n')
        
        # 식사 메뉴
        self.ordered_menu_text.delete(1.0, tk.END)
        for menu in business_info.ordered_items:
            line = f"{menu['name']}:{menu['price']}" if menu.get('price') else menu['name']
            self.ordered_menu_text.insert(tk.END, line + '\n')
        
        # 특징
        self.features_text.delete(1.0, tk.END)
        self.features_text.insert(1.0, '\n'.join(business_info.features))
        
        # 주차
        self.parking_text.delete(1.0, tk.END)
        self.parking_text.insert(1.0, business_info.parking_info)
    
    def get_business_info(self):
        """GUI에서 업체 정보 수집"""
        try:
            self.business_info.name = self.name_var.get().strip()
            self.business_info.short_name = self.short_name_var.get().strip()  # v7.5
            
            # 약칭이 없으면 자동 생성 (v7.5)
            if not self.business_info.short_name and self.business_info.name:
                self.business_info.short_name = generate_short_name(self.business_info.name)
                self.short_name_var.set(self.business_info.short_name)
            
            self.business_info.address = self.address_var.get().strip()
            self.business_info.hours = self.hours_var.get().strip()
            self.business_info.phone = self.phone_var.get().strip()
            self.business_info.atmosphere = self.atmosphere_var.get().strip()
            self.business_info.target_customer = self.target_customer_var.get().strip()
            
            # 메뉴 파싱
            menu_text = self.menu_text.get(1.0, tk.END).strip()
            self.business_info.menu_items = []
            for line in menu_text.split('\n'):
                if line.strip():
                    if ':' in line:
                        parts = line.split(':', 1)
                        self.business_info.menu_items.append({
                            "name": parts[0].strip(),
                            "price": parts[1].strip()
                        })
                    else:
                        self.business_info.menu_items.append({
                            "name": line.strip(),
                            "price": ""
                        })
            
            # 식사 메뉴 파싱
            ordered_text = self.ordered_menu_text.get(1.0, tk.END).strip()
            self.business_info.ordered_items = []
            for line in ordered_text.split('\n'):
                if line.strip():
                    if ':' in line:
                        parts = line.split(':', 1)
                        self.business_info.ordered_items.append({
                            "name": parts[0].strip(),
                            "price": parts[1].strip()
                        })
                    else:
                        self.business_info.ordered_items.append({
                            "name": line.strip(),
                            "price": ""
                        })
            
            # 특징
            features_text = self.features_text.get(1.0, tk.END).strip()
            self.business_info.features = [f.strip() for f in features_text.split('\n') if f.strip()]
            
            # 주차
            self.business_info.parking_info = self.parking_text.get(1.0, tk.END).strip()
            
            # 필수 항목 검증
            if not self.business_info.name:
                raise ValueError("업체명을 입력해주세요.")
            if not self.business_info.address:
                raise ValueError("주소를 입력해주세요.")
            if not self.business_info.menu_items and not self.business_info.features:
                raise ValueError("전체 메뉴나 주요 특징을 입력해주세요.")
            if not self.business_info.ordered_items:
                raise ValueError("식사 메뉴를 입력해주세요.")
            
            return True
            
        except ValueError as e:
            messagebox.showerror("입력 오류", str(e))
            return False
    
    def select_output_dir(self):
        """출력 디렉토리 선택"""
        directory = filedialog.askdirectory()
        if directory:
            self.output_var.set(directory)
    
    def start_processing(self):
        """처리 시작"""
        # 검증
        if not self.config.API_KEY or self.config.API_KEY == "your-api-key-here":
            messagebox.showerror("오류", "OpenAI API 키를 입력해주세요.")
            return
        
        if not self.processor or not self.processor.items:
            messagebox.showerror("오류", "CSV 파일을 먼저 로드해주세요.")
            return
        
        if not self.get_business_info():
            return
        
        # 설정 업데이트
        self.batch_config.preview_first = self.preview_var.get()
        self.batch_config.batch_mode = self.batch_mode_var.get()
        self.batch_config.max_retries = self.retry_var.get()
        self.batch_config.api_delay = self.delay_var.get()
        self.batch_config.output_base_dir = self.output_var.get()
        
        # 프로세서 업데이트
        self.processor.config = self.config
        self.processor.batch_config = self.batch_config
        self.processor.converter = BlogConverter(self.config)
        self.processor.set_business_info(self.business_info)
        
        # UI 상태 변경
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.pause_btn.config(state=tk.NORMAL)
        self.status_var.set("처리 중...")
        
        # 쓰레드 시작
        self.processing_thread = threading.Thread(target=self.run_processing)
        self.processing_thread.start()
    
    def run_processing(self):
        """처리 실행 (쓰레드)"""
        try:
            # 첫 번째 미리보기 (옵션)
            if self.batch_config.preview_first:
                # 첫 번째 항목만 처리
                first_item = self.processor.items[0]
                with open(first_item.original_file, 'r', encoding='utf-8') as f:
                    original_text = f.read()
                
                temp_business_info = BusinessInfo()
                for key, value in self.business_info.__dict__.items():
                    setattr(temp_business_info, key, value)
                temp_business_info.seo_keywords = [first_item.seo_keyword]
                
                result = self.processor.converter.convert(original_text, temp_business_info)
                
                if result['success']:
                    # 미리보기 표시
                    self.root.after(0, self.show_preview, result['result'], first_item.seo_keyword)
                    # 사용자 확인 대기
                    while hasattr(self, 'preview_waiting') and self.preview_waiting:
                        time.sleep(0.1)
                    
                    if hasattr(self, 'preview_cancelled') and self.preview_cancelled:
                        self.root.after(0, self.on_processing_cancelled)
                        return
            
            # 전체 처리
            summary = self.processor.process_all(
                progress_callback=self.update_progress,
                status_callback=self.update_item_status
            )
            
            # 완료
            self.root.after(0, self.on_processing_complete, summary)
            
        except Exception as e:
            self.root.after(0, self.on_processing_error, str(e))
    
    def show_preview(self, result: str, keyword: str):
        """첫 번째 결과 미리보기"""
        self.preview_waiting = True
        
        dialog = tk.Toplevel(self.root)
        dialog.title(f"미리보기: {keyword}")
        dialog.geometry("800x600")
        
        # 텍스트 표시
        text_widget = scrolledtext.ScrolledText(dialog, wrap=tk.WORD)
        text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        text_widget.insert(1.0, result)
        text_widget.config(state=tk.DISABLED)
        
        # 버튼
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=10)
        
        def on_continue():
            self.preview_waiting = False
            self.preview_cancelled = False
            dialog.destroy()
        
        def on_cancel():
            self.preview_waiting = False
            self.preview_cancelled = True
            dialog.destroy()
        
        ttk.Button(btn_frame, text="계속", command=on_continue).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="취소", command=on_cancel).pack(side=tk.LEFT, padx=5)
        
        dialog.protocol("WM_DELETE_WINDOW", on_cancel)
    
    def update_progress(self, current: int, total: int):
        """진행률 업데이트"""
        percentage = (current / total) * 100
        self.root.after(0, self._update_progress_ui, current, total, percentage)
    
    def _update_progress_ui(self, current: int, total: int, percentage: float):
        """진행률 UI 업데이트"""
        self.progress_var.set(percentage)
        self.progress_label.config(text=f"{current} / {total}")
        
        # 통계 업데이트
        if self.processor:
            success_count = sum(1 for item in self.processor.items if item.status == "success")
            failed_count = sum(1 for item in self.processor.items if item.status == "failed")
            
            self.stats_label.config(
                text=f"성공: {success_count} | 실패: {failed_count} | 대기: {total - current}"
            )
    
    def update_item_status(self, index: int, status: str, message: str):
        """항목 상태 업데이트"""
        self.root.after(0, self._update_item_status_ui, index, status, message)
    
    def _update_item_status_ui(self, index: int, status: str, message: str):
        """항목 상태 UI 업데이트"""
        # 트리뷰 업데이트
        item_id = self.items_tree.get_children()[index]
        values = list(self.items_tree.item(item_id)['values'])
        values[3] = status
        self.items_tree.item(item_id, values=values)
        
        # 색상 변경
        if status == "success":
            self.items_tree.item(item_id, tags=('success',))
        elif status == "failed":
            self.items_tree.item(item_id, tags=('failed',))
        elif status == "processing":
            self.items_tree.item(item_id, tags=('processing',))
        
        # 로그 추가
        self.log_message(f"[{index+1}] {status}: {message}")
        
        # 태그 설정
        self.items_tree.tag_configure('success', foreground='green')
        self.items_tree.tag_configure('failed', foreground='red')
        self.items_tree.tag_configure('processing', foreground='blue')
    
    def on_processing_complete(self, summary: Dict):
        """처리 완료"""
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.pause_btn.config(state=tk.DISABLED)
        self.status_var.set("완료")
        
        # 결과 표시
        messagebox.showinfo(
            "처리 완료",
            f"전체: {summary['total']}개\n"
            f"성공: {summary['success']}개\n"
            f"실패: {summary['failed']}개"
        )
        
        # 출력 폴더 열기
        output_dir = os.path.join(
            self.batch_config.output_base_dir,
            f"{summary['business_name']}_{summary['timestamp']}"
        )
        
        if os.name == 'nt':
            os.startfile(output_dir)
    
    def on_processing_cancelled(self):
        """처리 취소됨"""
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.pause_btn.config(state=tk.DISABLED)
        self.status_var.set("취소됨")
        self.log_message("사용자에 의해 처리가 취소되었습니다.")
    
    def on_processing_error(self, error: str):
        """처리 오류"""
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.pause_btn.config(state=tk.DISABLED)
        self.status_var.set("오류 발생")
        
        messagebox.showerror("처리 오류", error)
        self.log_message(f"오류: {error}")
    
    def stop_processing(self):
        """처리 중지"""
        if self.processor:
            self.processor.stop()
            self.status_var.set("중지 중...")
    
    def toggle_pause(self):
        """일시정지/재개"""
        if self.processor:
            if self.pause_btn['text'] == "일시정지":
                self.processor.pause()
                self.pause_btn.config(text="재개")
                self.status_var.set("일시정지")
            else:
                self.processor.resume()
                self.pause_btn.config(text="일시정지")
                self.status_var.set("처리 중...")
    
    def log_message(self, message: str):
        """로그 메시지 추가"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
    
    def run(self):
        """GUI 실행"""
        self.root.mainloop()


# ===== 메인 실행 =====
if __name__ == "__main__":
    app = EnhancedBatchGUI()
    app.run()