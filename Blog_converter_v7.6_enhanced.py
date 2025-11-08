"""
블로그 변환 프로그램 v7.6_enhanced - 필수 항목 + 프리셋 시스템
v7.6의 필수 항목 기능 + 프리셋 시스템 통합
- [필수] 항목 기능 (핵심 특징 보장)
- 15-25개 특징 권장
- 업체 정보 프리셋 저장/불러오기
- 예시 원고 드롭다운 선택
- SEO 키워드 프리셋
"""

import os
import re
import json
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk, simpledialog
import threading
import time

# 외부 라이브러리
try:
    from openai import OpenAI
except ImportError as e:
    print(f"필요한 라이브러리를 설치해주세요: pip install openai")
    raise e


# ===== 설정 클래스 =====
@dataclass
class Config:
    """프로그램 설정"""
    API_KEY: str = "your-api-key-here"
    MODEL: str = "gpt-4.1-2025-04-14"  # GPT-4.1 사용 (2025년 최신 모델)
    MAX_TOKENS: int = 4096
    TEMPERATURE: float = 0.7
    
    # 글자수 설정
    MIN_CHARS: int = 1200
    MAX_CHARS: int = 1500
    TARGET_CHARS: int = 1350
    
    # 제목 생성 설정
    TITLE_MODEL: str = "gpt-4.1-2025-04-14"  # 제목 생성용 모델 (같은 모델 사용)
    TITLE_MAX_TOKENS: int = 100
    TITLE_TEMPERATURE: float = 0.8  # 제목은 좀 더 창의적으로
    
    # 특징 선택 설정
    FEATURE_SELECT_MIN: int = 7      # 최소 선택 개수
    FEATURE_SELECT_MAX: int = 8      # 최대 선택 개수
    FEATURE_SELECT_SEED: Optional[int] = None  # 랜덤 시드 (None이면 매번 다름)
    
    # 프리셋 디렉토리
    PRESET_BASE_DIR: str = "프리셋"
    BUSINESS_PRESET_DIR: str = "프리셋/업체정보"
    EXAMPLE_DIR: str = "프리셋/예시원고"
    KEYWORD_PRESET_DIR: str = "프리셋/키워드셋"


# ===== 데이터 구조 =====
@dataclass
class StyleAnalysis:
    """말투 분석 결과"""
    endings: List[str] = field(default_factory=list)  # 종결어미
    expressions: List[str] = field(default_factory=list)  # 특징적 표현
    emotions: List[str] = field(default_factory=list)  # 감정 표현
    sentence_patterns: List[str] = field(default_factory=list)  # 문장 패턴
    marker_info: Dict = field(default_factory=dict)  # 마커 정보: (지도), (동영상)
    
    def to_prompt_description(self) -> str:
        """프롬프트용 설명 생성"""
        desc = []
        
        if self.endings:
            desc.append(f"종결어미: {', '.join(self.endings[:10])}")
        
        if self.expressions:
            desc.append(f"특징 표현: {', '.join(self.expressions[:10])}")
            
        if self.emotions:
            desc.append(f"감정 표현: {', '.join(self.emotions[:8])}")
            
        return '\n'.join(desc)


@dataclass
class BusinessInfo:
    """업체 정보"""
    name: str = ""
    short_name: str = ""  # 제목용 약칭 (v7.5 신규)
    seo_keywords: List[str] = field(default_factory=list)
    address: str = ""
    hours: str = ""
    phone: str = ""
    features: List[str] = field(default_factory=list)
    menu_items: List[Dict[str, str]] = field(default_factory=list)  # 전체 메뉴 리스트 [{"name": "메뉴명", "price": "가격"}]
    ordered_items: List[Dict[str, str]] = field(default_factory=list)  # 실제 식사한 메뉴 리스트 [{"name": "메뉴명", "price": "가격"}]
    atmosphere: str = ""
    target_customer: str = ""  # 타겟 고객층
    parking_info: str = ""  # 주차 정보
    reviews_count: Dict[str, int] = field(default_factory=dict)  # 리뷰 수 {"visitor": 0, "blog": 0}
    certifications: List[str] = field(default_factory=list)  # 인증 정보 (안심식당 등)
    accessibility: List[str] = field(default_factory=list)  # 접근성 정보 (휠체어 접근 등)
    
    def get_location_name(self) -> str:
        """주소에서 지역명 추출"""
        # 예: "경기 고양시 일산동구" → "일산"
        if "일산" in self.address:
            return "일산"
        elif "강남" in self.address:
            return "강남"
        elif "목포" in self.address:
            return "목포"
        else:
            # 첫 번째 구/시 이름 사용
            parts = self.address.split()
            if len(parts) >= 2:
                return parts[1].replace("시", "").replace("구", "")
        return ""


# ===== 프리셋 관리자 =====
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
            'short_name': business_info.short_name,  # v7.5 약칭 포함
            'seo_keywords': business_info.seo_keywords,
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
    
    def load_preset(self, filepath: str) -> BusinessInfo:
        """JSON에서 업체 정보 불러오기"""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        business_info = BusinessInfo()
        for key, value in data.items():
            if hasattr(business_info, key):
                setattr(business_info, key, value)
        
        return business_info
    
    def list_presets(self) -> List[str]:
        """저장된 프리셋 목록"""
        presets = []
        for file in os.listdir(self.preset_dir):
            if file.endswith('.json'):
                presets.append(file)
        return sorted(presets)


class KeywordPresetManager:
    """SEO 키워드 프리셋 관리"""
    
    def __init__(self, preset_dir: str):
        self.preset_dir = preset_dir
        os.makedirs(preset_dir, exist_ok=True)
    
    def save_preset(self, name: str, keywords: List[str]) -> str:
        """키워드 세트를 JSON으로 저장"""
        filepath = os.path.join(self.preset_dir, f"{name}.json")
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(keywords, f, ensure_ascii=False, indent=2)
        
        return filepath
    
    def load_preset(self, filename: str) -> List[str]:
        """JSON에서 키워드 세트 불러오기"""
        filepath = os.path.join(self.preset_dir, filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def list_presets(self) -> List[str]:
        """저장된 키워드 프리셋 목록"""
        presets = []
        for file in os.listdir(self.preset_dir):
            if file.endswith('.json'):
                presets.append(file)
        return sorted(presets)


class ExampleManager:
    """예시 원고 관리"""
    
    def __init__(self, example_dir: str):
        self.example_dir = example_dir
        os.makedirs(example_dir, exist_ok=True)
    
    def list_examples(self) -> List[str]:
        """예시 파일 목록"""
        examples = []
        for file in os.listdir(self.example_dir):
            if file.endswith('.txt'):
                examples.append(file)
        return sorted(examples)
    
    def load_example(self, filename: str) -> str:
        """예시 파일 내용 읽기"""
        filepath = os.path.join(self.example_dir, filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()


# ===== 유틸리티 함수 =====
def generate_short_name(full_name: str) -> str:
    """업체명에서 약칭 생성 (v7.5 기능)"""
    # 공백 제거
    name = full_name.strip()
    
    # 특수 케이스 처리
    if '칼국수' in name:
        if '대종' in name:
            return "대종칼국수"
        elif '명동' in name:
            return "명동칼국수"
    
    # 일반적인 약칭 생성 규칙
    # 1. 괄호 내용 제거
    name = re.sub(r'\([^)]*\)', '', name).strip()
    
    # 2. 지점명 제거
    for suffix in ['점', '지점', '본점', '분점']:
        if name.endswith(suffix):
            parts = name.rsplit(' ', 1)
            if len(parts) > 1:
                name = parts[0]
    
    # 3. 길이가 8자 이상이면 축약
    if len(name) > 8:
        # 공백으로 분리
        parts = name.split()
        if len(parts) > 1:
            # 첫 번째 부분만 사용
            name = parts[0]
    
    return name


# ===== 말투 분석기 =====
class StyleAnalyzer:
    """원본 텍스트의 말투와 스타일 분석"""
    
    def __init__(self):
        self.common_endings = ['니다', '어요', '아요', '죠', '는데', '네요', '거든요', '더라고요', '습니다', '해요']
    
    def analyze(self, text: str) -> StyleAnalysis:
        """텍스트 분석하여 스타일 추출"""
        analysis = StyleAnalysis()
        
        # 문장 분리 (마침표, 느낌표, 물음표 기준)
        sentences = re.split(r'[.!?]+', text)
        
        # 종결어미 분석
        for sentence in sentences:
            sentence = sentence.strip()
            if sentence:
                # 종결어미 추출
                for ending in self.common_endings:
                    if sentence.endswith(ending):
                        analysis.endings.append(ending)
                        break
                
                # 감정 표현 찾기
                emotions = re.findall(r'[♥♡★☆~!]{2,}|ㅎㅎ|ㅋㅋ|^^|ㅠㅠ', sentence)
                analysis.emotions.extend(emotions)
        
        # 특징적 표현 찾기
        expressions = []
        # 강조 표현
        expressions.extend(re.findall(r'정말|진짜|너무|완전|대박|최고', text))
        # 감탄사
        expressions.extend(re.findall(r'와[~!]*|우와[~!]*|오[~!]+', text))
        
        analysis.expressions = list(set(expressions))  # 중복 제거
        
        # 마커 정보 추출
        if '(지도)' in text:
            analysis.marker_info['map'] = True
        if '(동영상)' in text:
            analysis.marker_info['video'] = True
        
        return analysis


# ===== 특징 선택기 =====
class FeatureSelector:
    """특징 랜덤 선택기"""
    
    def __init__(self, min_count: int = 7, max_count: int = 8):
        self.min_count = min_count
        self.max_count = max_count
    
    def select_features(self, features: List[str], seed: Optional[int] = None) -> List[str]:
        """특징 리스트에서 랜덤하게 선택"""
        if not features:
            return []
        
        # 특징이 min_count보다 적으면 모두 반환
        if len(features) <= self.min_count:
            return features
        
        # 랜덤 시드 설정
        if seed is not None:
            random.seed(seed)
        
        # 선택할 개수 결정 (min_count ~ max_count)
        count = random.randint(self.min_count, min(self.max_count, len(features)))
        
        # 랜덤 선택
        selected = random.sample(features, count)
        
        return selected


# ===== 프롬프트 빌더 =====
class PromptBuilder:
    """변환용 프롬프트 생성"""
    
    def __init__(self, feature_selector: Optional[FeatureSelector] = None):
        self.feature_selector = feature_selector or FeatureSelector()
    
    def build_conversion_prompt(self, original_text: str, style_analysis: StyleAnalysis, 
                              business_info: BusinessInfo, feature_seed: Optional[int] = None) -> str:
        """변환 프롬프트 생성"""
        
        # 지역명 변환
        location = business_info.get_location_name()
        
        # 전체 메뉴 정보 포맷팅
        all_menu_str = ""
        if business_info.menu_items:
            menu_list = []
            for menu in business_info.menu_items:  # 모든 메뉴 표시
                if menu.get('price'):
                    menu_list.append(f"{menu['name']} ({menu['price']})")
                else:
                    menu_list.append(menu['name'])
            all_menu_str = ', '.join(menu_list)
        
        # 식사한 메뉴 정보 포맷팅
        ordered_menu_str = ""
        if business_info.ordered_items:
            ordered_list = []
            for menu in business_info.ordered_items:
                if menu.get('price'):
                    ordered_list.append(f"{menu['name']} ({menu['price']})")
                else:
                    ordered_list.append(menu['name'])
            ordered_menu_str = ', '.join(ordered_list)
        
        # 특징 선택
        selected_features = self.feature_selector.select_features(
            business_info.features, 
            seed=feature_seed
        )
        
        # 글자수 계산
        char_count = len(original_text.replace(' ', '').replace('\n', ''))
        
        prompt = f"""다음 블로그를 정확히 분석하고, 동일한 말투와 감성으로 새로운 업체를 소개해주세요.

[원본 블로그]
{original_text}

[원본의 말투 특징]
{style_analysis.to_prompt_description()}

[새로운 업체 정보]
업체명: {business_info.name}
위치: {location} ({business_info.address})
전체 메뉴: {all_menu_str if all_menu_str else selected_features[0] if selected_features else ''}
실제 주문한 메뉴: {ordered_menu_str if ordered_menu_str else '메뉴 정보 없음'}
운영시간: {business_info.hours}
전화번호: {business_info.phone}
특징: {', '.join(selected_features) if selected_features else ''}
분위기: {business_info.atmosphere}
타겟 고객: {business_info.target_customer}
주차 정보: {business_info.parking_info}
SEO 키워드: {', '.join(business_info.seo_keywords[:5])}

[변환 규칙]
1. 원본과 100% 동일한 말투 유지 (종결어미, 감탄사, 구어체 표현)
2. 원본과 동일한 감정 표현과 감성 유지
3. 원본과 비슷한 문장 길이와 리듬 유지
4. 원본의 특징적인 표현들을 그대로 활용
5. 글자수: 1,350자 (±150자) - 반드시 1,200-1,500자 사이로 작성
6. SEO 키워드를 자연스럽게 5-7회 분산
7. 원본이 길더라도 핵심 내용을 압축하여 지정된 글자수를 준수하세요"""
        
        # 메뉴 관련 지시사항 추가
        if business_info.ordered_items:
            prompt += f"""
8. 메뉴 작성 방법:
   - 처음에 전체 메뉴를 보고 다양함에 놀란 반응 표현
   - "메뉴가 정말 다양하더라구요", "메뉴판 보니 놀랍더라구여" 등
   - 고민 끝에 실제 주문한 메뉴({ordered_menu_str})를 선택했다고 작성
   - 주문한 메뉴들에 대해서만 맛과 특징을 상세히 설명
   - 먹지 않은 메뉴는 "다음에 먹어보고 싶다" 정도로만 언급"""
        
        # 마커 관련 지시사항 추가
        if style_analysis.marker_info.get('has_map') or style_analysis.marker_info.get('has_video'):
            prompt += "\n9. 원본의 (지도), (동영상) 마커를 비슷한 위치에 포함하세요:"
            prompt += "\n   **중요: 정확히 (지도), (동영상) 형식으로만 작성하고, (지도삽입) 등의 변형은 사용하지 마세요**"
            
            if style_analysis.marker_info.get('has_map'):
                map_positions = style_analysis.marker_info['map_positions']
                prompt += f"\n   - (지도) 마커: 원본의 약 {int(map_positions[0]['relative_position']*100)}% 위치"
            
            if style_analysis.marker_info.get('has_video'):
                video_positions = style_analysis.marker_info['video_positions'] 
                prompt += f"\n   - (동영상) 마커: 원본의 약 {int(video_positions[0]['relative_position']*100)}% 위치"
        
        prompt += "\n\n제목은 생성하지 마세요. 본문만 작성하세요."

        return prompt
    
    def build_title_prompt(self, keyword: str, business_info: BusinessInfo) -> str:
        """제목 생성 프롬프트 (v7.5 신규)"""
        name_to_use = business_info.short_name if business_info.short_name else business_info.name
        
        prompt = f"""다음 조건에 맞는 자연스러운 블로그 제목을 5개 생성해주세요:

키워드: {keyword}
업체명: {name_to_use}
지역: {business_info.get_location_name()}

요구사항:
1. 20-40자 사이
2. 키워드를 자연스럽게 포함
3. 클릭하고 싶은 매력적인 제목
4. 다양한 스타일로 작성

형식: 한 줄에 하나씩, 번호 없이 제목만 작성"""

        return prompt


# ===== API 핸들러 =====
class OpenAIAPIHandler:
    """OpenAI API 통신 처리"""
    
    def __init__(self, config: Config):
        self.config = config
        self.client = OpenAI(api_key=config.API_KEY)
    
    def convert_blog(self, prompt: str) -> str:
        """블로그 변환 API 호출"""
        try:
            response = self.client.chat.completions.create(
                model=self.config.MODEL,
                messages=[
                    {"role": "system", "content": "당신은 블로그 작성 전문가입니다."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=self.config.MAX_TOKENS,
                temperature=self.config.TEMPERATURE
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            raise Exception(f"API 호출 오류: {str(e)}")
    
    def generate_title(self, prompt: str) -> str:
        """제목 생성 API 호출 (v7.5 신규)"""
        try:
            response = self.client.chat.completions.create(
                model=self.config.TITLE_MODEL,
                messages=[
                    {"role": "system", "content": "당신은 매력적인 블로그 제목을 만드는 전문가입니다."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=self.config.TITLE_MAX_TOKENS,
                temperature=self.config.TITLE_TEMPERATURE
            )
            
            # 첫 번째 제목 선택
            titles = response.choices[0].message.content.strip().split('\n')
            return titles[0].strip() if titles else ""
            
        except Exception as e:
            raise Exception(f"제목 생성 API 오류: {str(e)}")


# ===== 마커 처리기 =====
class MarkerProcessor:
    """(지도), (동영상) 등 마커 처리"""
    
    def process(self, text: str, marker_info: Dict, business_info: BusinessInfo) -> str:
        """마커 위치에 맞게 텍스트 조정"""
        
        # (지도) 마커 처리
        if marker_info.get('map') and '(지도)' not in text:
            # 주소 언급 부분 뒤에 (지도) 추가
            if business_info.address:
                address_part = business_info.address.split()[0]  # 첫 번째 주소 부분
                if address_part in text:
                    text = text.replace(address_part, f"{address_part} (지도)", 1)
        
        # (동영상) 마커는 원본에 있었다면 유지
        
        return text


# ===== 블로그 변환기 =====
class BlogConverter:
    """블로그 변환 메인 클래스"""
    
    def __init__(self, config: Config):
        self.config = config
        self.style_analyzer = StyleAnalyzer()
        self.feature_selector = FeatureSelector(
            min_count=config.FEATURE_SELECT_MIN,
            max_count=config.FEATURE_SELECT_MAX
        )
        self.prompt_builder = PromptBuilder(self.feature_selector)
        self.api_handler = OpenAIAPIHandler(config)
        self.marker_processor = MarkerProcessor()
        self.generated_titles = set()  # 중복 방지용 (v7.5 신규)
    
    def convert(self, original_text: str, business_info: BusinessInfo) -> Dict:
        """블로그 변환 실행"""
        try:
            # 1. 말투 분석
            style_analysis = self.style_analyzer.analyze(original_text)
            
            # 2. 프롬프트 생성
            prompt = self.prompt_builder.build_conversion_prompt(
                original_text, style_analysis, business_info,
                feature_seed=self.config.FEATURE_SELECT_SEED
            )
            
            # 3. API 호출
            result = self.api_handler.convert_blog(prompt)
            
            # 4. 마커 후처리 (필요시)
            if style_analysis.marker_info:
                result = self.marker_processor.process(result, style_analysis.marker_info, business_info)
            
            # 5. 결과 검증 (제목 추가 전에 수행)
            validation = self._validate_result(result, original_text, business_info)
            
            # 6. 스마트 제목 생성 (v7.5 개선)
            if business_info.seo_keywords:
                title = self._generate_blog_title(
                    business_info.seo_keywords[0], 
                    business_info
                )
                result = f"제목:{title}\n\n" + result
            
            return {
                'success': True,
                'result': result,
                'style_analysis': style_analysis,
                'validation': validation
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'result': ''
            }
    
    def _generate_blog_title(self, keyword: str, business_info: BusinessInfo) -> str:
        """AI를 활용한 자연스러운 제목 생성 (v7.5 신규)"""
        
        try:
            # 제목 생성 프롬프트 빌드
            title_prompt = self.prompt_builder.build_title_prompt(keyword, business_info)
            
            # API 호출로 제목 생성
            generated_title = self.api_handler.generate_title(title_prompt)
            
            if generated_title:
                # 검증: 길이 체크
                if 20 <= len(generated_title) <= 40:
                    # 검증: 키워드 포함 여부
                    if keyword in generated_title:
                        # 검증: 중복 체크
                        if generated_title not in self.generated_titles:
                            self.generated_titles.add(generated_title)
                            return generated_title
                
                # 검증 실패시 다시 시도 (1회)
                generated_title = self.api_handler.generate_title(title_prompt)
                if generated_title and 20 <= len(generated_title) <= 40:
                    self.generated_titles.add(generated_title)
                    return generated_title
        
        except Exception as e:
            print(f"제목 생성 오류: {str(e)}")
        
        # Fallback: 템플릿 기반 제목 생성
        return self._generate_fallback_title(keyword, business_info)
    
    def _generate_fallback_title(self, keyword: str, business_info: BusinessInfo) -> str:
        """Fallback 제목 생성 (API 실패시)"""
        name_to_use = business_info.short_name if business_info.short_name else business_info.name
        
        templates = [
            f"{keyword} {name_to_use}에서 든든한 한끼 식사",
            f"{keyword} {name_to_use} 방문 후기",
            f"{name_to_use} 맛집 탐방 {keyword} 추천",
            f"{keyword} {name_to_use}의 특별한 메뉴",
            f"{name_to_use}에서 만난 {keyword}의 맛"
        ]
        
        # 랜덤하게 하나 선택
        title = random.choice(templates)
        
        # 길이 체크
        if len(title) > 40:
            # 너무 길면 단순화
            title = f"{keyword} {name_to_use} 방문기"
        
        return title
    
    def _validate_result(self, result: str, original: str, business_info: BusinessInfo) -> Dict:
        """결과 검증"""
        validation = {}
        
        # 글자수
        result_chars = len(result.replace(' ', '').replace('\n', ''))
        original_chars = len(original.replace(' ', '').replace('\n', ''))
        validation['char_count'] = result_chars
        validation['char_diff'] = abs(result_chars - original_chars)
        validation['char_valid'] = validation['char_diff'] < 200
        
        # SEO 키워드
        keyword_counts = {}
        for keyword in business_info.seo_keywords:
            keyword_counts[keyword] = result.count(keyword)
        
        validation['seo_keywords'] = keyword_counts
        validation['seo_total'] = sum(keyword_counts.values())
        validation['seo_valid'] = 5 <= validation['seo_total'] <= 10
        
        # 반복 검사
        sentences = re.split(r'[.!?]\s*', result)
        seen = set()
        repeated = []
        
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) > 20:
                if sentence in seen:
                    repeated.append(sentence)
                seen.add(sentence)
        
        validation['has_repetition'] = len(repeated) > 0
        validation['repeated_sentences'] = repeated
        
        return validation


# ===== GUI 인터페이스 =====
class BlogConverterGUI:
    """블로그 변환 프로그램 GUI"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("블로그 변환 프로그램 v7.6_enhanced - 필수 항목 + 프리셋")
        self.root.geometry("1400x900")
        
        # 설정
        self.config = Config()
        self.converter = None
        self.original_text = ""
        self.business_info = BusinessInfo()
        
        # 프리셋 관리자
        self.business_manager = BusinessInfoManager(self.config.BUSINESS_PRESET_DIR)
        self.keyword_manager = KeywordPresetManager(self.config.KEYWORD_PRESET_DIR)
        self.example_manager = ExampleManager(self.config.EXAMPLE_DIR)
        
        self.setup_ui()
        self.load_config()
    
    def setup_ui(self):
        """UI 구성"""
        # 메인 프레임
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 상단: API 키 입력
        api_frame = ttk.LabelFrame(main_frame, text="API 설정", padding="10")
        api_frame.grid(row=0, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)
        
        ttk.Label(api_frame, text="OpenAI API Key:").grid(row=0, column=0, sticky=tk.W)
        self.api_key_var = tk.StringVar()
        api_key_entry = ttk.Entry(api_frame, textvariable=self.api_key_var, width=50, show="*")
        api_key_entry.grid(row=0, column=1, padx=5)
        
        ttk.Button(api_frame, text="API 키 저장", command=self.save_config).grid(row=0, column=2)
        
        # 중앙: 3단 레이아웃
        # 1. 원본 입력
        original_frame = ttk.LabelFrame(main_frame, text="원본 블로그", padding="10")
        original_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5)
        
        self.original_text_widget = scrolledtext.ScrolledText(
            original_frame, width=40, height=35, wrap=tk.WORD, font=("맑은 고딕", 10)
        )
        self.original_text_widget.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        btn_frame1 = ttk.Frame(original_frame)
        btn_frame1.grid(row=1, column=0, pady=5)
        ttk.Button(btn_frame1, text="파일 열기", command=self.load_file).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame1, text="예시 선택", command=self.load_example_dropdown).pack(side=tk.LEFT)
        
        # 2. 업체 정보 입력
        info_frame = ttk.LabelFrame(main_frame, text="업체 정보 입력", padding="10")
        info_frame.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5)
        
        # 프리셋 버튼들
        preset_frame = ttk.Frame(info_frame)
        preset_frame.grid(row=0, column=0, columnspan=2, pady=5)
        ttk.Button(preset_frame, text="프리셋 불러오기", command=self.load_business_preset).pack(side=tk.LEFT, padx=5)
        ttk.Button(preset_frame, text="현재 설정 저장", command=self.save_business_preset).pack(side=tk.LEFT)
        
        # 입력 필드들
        row = 1
        
        # 업체명
        ttk.Label(info_frame, text="업체명*:").grid(row=row, column=0, sticky=tk.W, pady=5)
        self.name_var = tk.StringVar()
        name_entry = ttk.Entry(info_frame, textvariable=self.name_var, width=35)
        name_entry.grid(row=row, column=1, pady=5)
        # 업체명 변경시 약칭 자동 생성 (v7.5 신규)
        name_entry.bind('<FocusOut>', self.on_name_change)
        row += 1
        
        # 제목용 약칭 (v7.5 신규)
        ttk.Label(info_frame, text="제목용 약칭:").grid(row=row, column=0, sticky=tk.W, pady=5)
        self.short_name_var = tk.StringVar()
        short_name_entry = ttk.Entry(info_frame, textvariable=self.short_name_var, width=35)
        short_name_entry.grid(row=row, column=1, pady=5)
        ttk.Label(info_frame, text="(자동생성됨, 수정가능)", font=("맑은 고딕", 8)).grid(row=row, column=2, sticky=tk.W, padx=5)
        row += 1
        
        # SEO 키워드
        ttk.Label(info_frame, text="SEO 키워드*\n(쉼표구분):").grid(row=row, column=0, sticky=tk.W, pady=5)
        
        # 키워드 입력 프레임
        keyword_frame = ttk.Frame(info_frame)
        keyword_frame.grid(row=row, column=1, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        self.seo_var = tk.StringVar()
        self.seo_entry = ttk.Entry(keyword_frame, textvariable=self.seo_var, width=25)
        self.seo_entry.pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(keyword_frame, text="프리셋", command=self.load_keyword_preset).pack(side=tk.LEFT)
        row += 1
        
        # 주소
        ttk.Label(info_frame, text="주소*:").grid(row=row, column=0, sticky=tk.W, pady=5)
        self.address_var = tk.StringVar()
        ttk.Entry(info_frame, textvariable=self.address_var, width=35).grid(row=row, column=1, pady=5)
        row += 1
        
        # 운영시간
        ttk.Label(info_frame, text="운영시간:").grid(row=row, column=0, sticky=tk.W, pady=5)
        self.hours_var = tk.StringVar()
        ttk.Entry(info_frame, textvariable=self.hours_var, width=35).grid(row=row, column=1, pady=5)
        row += 1
        
        # 전화번호
        ttk.Label(info_frame, text="전화번호:").grid(row=row, column=0, sticky=tk.W, pady=5)
        self.phone_var = tk.StringVar()
        ttk.Entry(info_frame, textvariable=self.phone_var, width=35).grid(row=row, column=1, pady=5)
        row += 1
        
        # 전체 메뉴 (기존 대표 메뉴를 전체 메뉴로 변경)
        ttk.Label(info_frame, text="전체 메뉴*\n(형식: 메뉴명:가격):").grid(row=row, column=0, sticky=tk.W, pady=5)
        self.menu_text = tk.Text(info_frame, width=35, height=3)
        self.menu_text.grid(row=row, column=1, pady=5)
        row += 1
        
        # 식사 메뉴 (새로 추가)
        ttk.Label(info_frame, text="식사 메뉴*\n(실제 주문한 메뉴):").grid(row=row, column=0, sticky=tk.W, pady=5)
        self.ordered_menu_text = tk.Text(info_frame, width=35, height=3)
        self.ordered_menu_text.grid(row=row, column=1, pady=5)
        row += 1
        
        # 주요 특징
        ttk.Label(info_frame, text="주요 특징*\n(줄바꿈구분):").grid(row=row, column=0, sticky=tk.W, pady=5)
        self.features_text = tk.Text(info_frame, width=35, height=3)
        self.features_text.grid(row=row, column=1, pady=5)
        row += 1
        
        # 분위기
        ttk.Label(info_frame, text="분위기:").grid(row=row, column=0, sticky=tk.W, pady=5)
        self.atmosphere_var = tk.StringVar()
        ttk.Entry(info_frame, textvariable=self.atmosphere_var, width=35).grid(row=row, column=1, pady=5)
        row += 1
        
        # 타겟 고객
        ttk.Label(info_frame, text="타겟 고객:").grid(row=row, column=0, sticky=tk.W, pady=5)
        self.target_customer_var = tk.StringVar()
        ttk.Entry(info_frame, textvariable=self.target_customer_var, width=35).grid(row=row, column=1, pady=5)
        row += 1
        
        # 주차 정보
        ttk.Label(info_frame, text="주차 정보:").grid(row=row, column=0, sticky=tk.W, pady=5)
        self.parking_text = tk.Text(info_frame, width=35, height=2)
        self.parking_text.grid(row=row, column=1, pady=5)
        row += 1
        
        # 업체정보 파일 로드 버튼
        load_info_btn = ttk.Button(
            info_frame, text="업체정보 파일 열기", command=self.load_business_info_file
        )
        load_info_btn.grid(row=row, column=0, columnspan=2, pady=5)
        row += 1
        
        # 변환 버튼
        convert_btn = ttk.Button(
            info_frame, text="변환 시작", command=self.start_conversion,
            style="Accent.TButton"
        )
        convert_btn.grid(row=row, column=0, columnspan=2, pady=10)
        
        # 말투 분석 표시
        self.style_label = ttk.Label(info_frame, text="", wraplength=300)
        self.style_label.grid(row=row+1, column=0, columnspan=2, pady=5)
        
        # 3. 결과 출력
        result_frame = ttk.LabelFrame(main_frame, text="변환 결과", padding="10")
        result_frame.grid(row=1, column=2, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5)
        
        self.result_text_widget = scrolledtext.ScrolledText(
            result_frame, width=40, height=35, wrap=tk.WORD, font=("맑은 고딕", 10)
        )
        self.result_text_widget.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        btn_frame2 = ttk.Frame(result_frame)
        btn_frame2.grid(row=1, column=0, pady=5)
        ttk.Button(btn_frame2, text="결과 복사", command=self.copy_result).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame2, text="결과 저장", command=self.save_result).pack(side=tk.LEFT)
        
        # 하단: 상태바
        self.status_frame = ttk.Frame(main_frame)
        self.status_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)
        
        self.status_label = ttk.Label(self.status_frame, text="준비됨")
        self.status_label.pack(side=tk.LEFT)
        
        self.progress = ttk.Progressbar(self.status_frame, mode='indeterminate')
        
        # 그리드 가중치 설정
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.columnconfigure(2, weight=1)
        main_frame.rowconfigure(1, weight=1)
        
        # 스타일 설정
        style = ttk.Style()
        style.configure("Accent.TButton", foreground="blue")
    
    def on_name_change(self, event):
        """업체명 변경시 약칭 자동 생성 (v7.5 신규)"""
        full_name = self.name_var.get().strip()
        if full_name and not self.short_name_var.get():
            # 약칭이 비어있을 때만 자동 생성
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
                    self.update_status("설정을 로드했습니다.")
            except:
                pass
    
    def save_config(self):
        """설정 저장"""
        self.config.API_KEY = self.api_key_var.get()
        
        config_data = {'api_key': self.config.API_KEY}
        with open("blog_converter_config.json", 'w', encoding='utf-8') as f:
            json.dump(config_data, f)
        
        self.update_status("API 키가 저장되었습니다.")
        self.converter = BlogConverter(self.config)
    
    def load_file(self):
        """파일 열기"""
        filename = filedialog.askopenfilename(
            title="원본 블로그 파일 선택",
            filetypes=[("텍스트 파일", "*.txt"), ("모든 파일", "*.*")]
        )
        
        if filename:
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    self.original_text = f.read()
                    self.original_text_widget.delete(1.0, tk.END)
                    self.original_text_widget.insert(1.0, self.original_text)
                self.update_status(f"파일을 불러왔습니다: {os.path.basename(filename)}")
            except Exception as e:
                messagebox.showerror("오류", f"파일을 읽을 수 없습니다: {str(e)}")
    
    def load_example_dropdown(self):
        """예시 파일 드롭다운 선택"""
        examples = self.example_manager.list_examples()
        
        if not examples:
            messagebox.showinfo("알림", "예시 파일이 없습니다.")
            return
        
        # 선택 다이얼로그
        dialog = tk.Toplevel(self.root)
        dialog.title("예시 선택")
        dialog.geometry("400x300")
        
        ttk.Label(dialog, text="예시 파일을 선택하세요:").pack(pady=10)
        
        listbox = tk.Listbox(dialog, height=10)
        listbox.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        for example in examples:
            listbox.insert(tk.END, example)
        
        def on_select():
            selection = listbox.curselection()
            if selection:
                filename = listbox.get(selection[0])
                try:
                    content = self.example_manager.load_example(filename)
                    self.original_text_widget.delete(1.0, tk.END)
                    self.original_text_widget.insert(1.0, content)
                    self.update_status(f"예시를 불러왔습니다: {filename}")
                    dialog.destroy()
                except Exception as e:
                    messagebox.showerror("오류", f"예시 파일을 읽을 수 없습니다: {str(e)}")
        
        ttk.Button(dialog, text="선택", command=on_select).pack(pady=10)
    
    def load_business_preset(self):
        """업체정보 프리셋 불러오기"""
        presets = self.business_manager.list_presets()
        
        if not presets:
            messagebox.showinfo("알림", "저장된 프리셋이 없습니다.")
            return
        
        # 선택 다이얼로그
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
                filename = listbox.get(selection[0])
                try:
                    filepath = os.path.join(self.config.BUSINESS_PRESET_DIR, filename)
                    business_info = self.business_manager.load_preset(filepath)
                    self.apply_business_info(business_info)
                    self.update_status(f"프리셋을 불러왔습니다: {filename}")
                    dialog.destroy()
                except Exception as e:
                    messagebox.showerror("오류", f"프리셋을 불러올 수 없습니다: {str(e)}")
        
        ttk.Button(dialog, text="선택", command=on_select).pack(pady=10)
    
    def save_business_preset(self):
        """현재 업체정보를 프리셋으로 저장"""
        if not self.get_business_info():
            return
        
        # 파일명 입력
        filename = simpledialog.askstring("프리셋 저장", "프리셋 이름을 입력하세요:")
        if not filename:
            return
        
        if not filename.endswith('.json'):
            filename += '.json'
        
        try:
            filepath = self.business_manager.save_preset(self.business_info, filename)
            self.update_status(f"프리셋이 저장되었습니다: {filename}")
            messagebox.showinfo("완료", "프리셋이 저장되었습니다.")
        except Exception as e:
            messagebox.showerror("오류", f"프리셋 저장 실패: {str(e)}")
    
    def load_keyword_preset(self):
        """키워드 프리셋 선택"""
        presets = self.keyword_manager.list_presets()
        
        if not presets:
            messagebox.showinfo("알림", "저장된 키워드 프리셋이 없습니다.")
            return
        
        # 선택 다이얼로그
        dialog = tk.Toplevel(self.root)
        dialog.title("키워드 프리셋 선택")
        dialog.geometry("400x300")
        
        ttk.Label(dialog, text="키워드 프리셋을 선택하세요:").pack(pady=10)
        
        listbox = tk.Listbox(dialog, height=10)
        listbox.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        for preset in presets:
            listbox.insert(tk.END, preset)
        
        def on_select():
            selection = listbox.curselection()
            if selection:
                filename = listbox.get(selection[0])
                try:
                    keywords = self.keyword_manager.load_preset(filename)
                    self.seo_var.set(', '.join(keywords))
                    self.update_status(f"키워드 프리셋을 불러왔습니다: {filename}")
                    dialog.destroy()
                except Exception as e:
                    messagebox.showerror("오류", f"키워드 프리셋을 불러올 수 없습니다: {str(e)}")
        
        ttk.Button(dialog, text="선택", command=on_select).pack(pady=10)
    
    def apply_business_info(self, business_info: BusinessInfo):
        """업체정보를 UI에 적용"""
        self.name_var.set(business_info.name)
        self.short_name_var.set(business_info.short_name)
        self.seo_var.set(', '.join(business_info.seo_keywords))
        self.address_var.set(business_info.address)
        self.hours_var.set(business_info.hours)
        self.phone_var.set(business_info.phone)
        self.atmosphere_var.set(business_info.atmosphere)
        self.target_customer_var.set(business_info.target_customer)
        
        # 전체 메뉴
        self.menu_text.delete(1.0, tk.END)
        menu_lines = []
        for item in business_info.menu_items:
            if item['price']:
                menu_lines.append(f"{item['name']}:{item['price']}")
            else:
                menu_lines.append(item['name'])
        self.menu_text.insert(1.0, '\n'.join(menu_lines))
        
        # 식사 메뉴
        self.ordered_menu_text.delete(1.0, tk.END)
        ordered_lines = []
        for item in business_info.ordered_items:
            if item['price']:
                ordered_lines.append(f"{item['name']}:{item['price']}")
            else:
                ordered_lines.append(item['name'])
        self.ordered_menu_text.insert(1.0, '\n'.join(ordered_lines))
        
        # 특징
        self.features_text.delete(1.0, tk.END)
        self.features_text.insert(1.0, '\n'.join(business_info.features))
        
        # 주차 정보
        self.parking_text.delete(1.0, tk.END)
        self.parking_text.insert(1.0, business_info.parking_info)
    
    def get_business_info(self):
        """입력된 업체 정보 수집"""
        try:
            self.business_info.name = self.name_var.get().strip()
            self.business_info.short_name = self.short_name_var.get().strip()  # v7.5 신규
            
            # SEO 키워드
            keywords_str = self.seo_var.get().strip()
            self.business_info.seo_keywords = [k.strip() for k in keywords_str.split(',') if k.strip()]
            
            self.business_info.address = self.address_var.get().strip()
            self.business_info.hours = self.hours_var.get().strip()
            self.business_info.phone = self.phone_var.get().strip()
            self.business_info.atmosphere = self.atmosphere_var.get().strip()
            self.business_info.target_customer = self.target_customer_var.get().strip()
            
            # 전체 메뉴 (형식: 메뉴명:가격)
            menu_text = self.menu_text.get(1.0, tk.END).strip()
            menu_lines = [m.strip() for m in menu_text.split('\n') if m.strip()]
            self.business_info.menu_items = []
            for menu_line in menu_lines:
                if ':' in menu_line:
                    parts = menu_line.split(':', 1)
                    self.business_info.menu_items.append({
                        "name": parts[0].strip(),
                        "price": parts[1].strip()
                    })
                else:
                    # 가격 정보 없는 경우
                    self.business_info.menu_items.append({
                        "name": menu_line.strip(),
                        "price": ""
                    })
            
            # 식사 메뉴 (실제 주문한 메뉴)
            ordered_text = self.ordered_menu_text.get(1.0, tk.END).strip()
            ordered_lines = [m.strip() for m in ordered_text.split('\n') if m.strip()]
            self.business_info.ordered_items = []
            for menu_line in ordered_lines:
                if ':' in menu_line:
                    parts = menu_line.split(':', 1)
                    self.business_info.ordered_items.append({
                        "name": parts[0].strip(),
                        "price": parts[1].strip()
                    })
                else:
                    # 가격 정보 없는 경우
                    self.business_info.ordered_items.append({
                        "name": menu_line.strip(),
                        "price": ""
                    })
            
            # 특징
            features_text = self.features_text.get(1.0, tk.END).strip()
            self.business_info.features = [f.strip() for f in features_text.split('\n') if f.strip()]
            
            # 주차 정보
            parking_text = self.parking_text.get(1.0, tk.END).strip()
            self.business_info.parking_info = parking_text
            
            # 필수 항목 검증
            if not self.business_info.name:
                raise ValueError("업체명을 입력해주세요.")
            if not self.business_info.seo_keywords:
                raise ValueError("SEO 키워드를 입력해주세요.")
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
    
    def start_conversion(self):
        """변환 시작"""
        # 원본 텍스트 확인
        self.original_text = self.original_text_widget.get(1.0, tk.END).strip()
        if not self.original_text:
            messagebox.showerror("오류", "원본 블로그 텍스트를 입력해주세요.")
            return
        
        # 업체 정보 수집
        if not self.get_business_info():
            return
        
        # API 키 확인
        if not self.config.API_KEY or self.config.API_KEY == "your-api-key-here":
            messagebox.showerror("오류", "OpenAI API 키를 입력해주세요.")
            return
        
        # 변환기 초기화
        if not self.converter:
            self.converter = BlogConverter(self.config)
        
        # 비동기 변환 시작
        self.update_status("변환 중... (제목 생성 포함)")
        self.progress.pack(side=tk.LEFT, padx=10)
        self.progress.start()
        
        # 쓰레드에서 실행
        thread = threading.Thread(target=self.run_conversion)
        thread.start()
    
    def run_conversion(self):
        """변환 실행 (쓰레드)"""
        try:
            # 변환 수행
            result = self.converter.convert(self.original_text, self.business_info)
            
            # UI 업데이트 (메인 쓰레드에서)
            self.root.after(0, self.display_result, result)
            
        except Exception as e:
            self.root.after(0, self.show_error, str(e))
    
    def display_result(self, result: Dict):
        """결과 표시"""
        self.progress.stop()
        self.progress.pack_forget()
        
        if result['success']:
            # 결과 표시
            self.result_text_widget.delete(1.0, tk.END)
            self.result_text_widget.insert(1.0, result['result'])
            
            # 말투 분석 표시
            if 'style_analysis' in result:
                style = result['style_analysis']
                style_text = f"말투 분석: 종결어미 {len(style.endings)}개, 감정표현 {len(style.emotions)}개 발견"
                self.style_label.config(text=style_text)
            
            # 검증 결과
            validation = result.get('validation', {})
            status_msg = f"변환 완료! 글자수: {validation.get('char_count', 0)}자"
            
            if validation.get('has_repetition'):
                status_msg += " (경고: 반복 문장 발견)"
            
            self.update_status(status_msg)
            
        else:
            self.show_error(result.get('error', '알 수 없는 오류'))
    
    def show_error(self, error_msg: str):
        """오류 표시"""
        self.progress.stop()
        self.progress.pack_forget()
        self.update_status(f"오류 발생: {error_msg}")
        messagebox.showerror("변환 오류", error_msg)
    
    def copy_result(self):
        """결과 복사"""
        result = self.result_text_widget.get(1.0, tk.END).strip()
        if result:
            self.root.clipboard_clear()
            self.root.clipboard_append(result)
            self.update_status("결과를 클립보드에 복사했습니다.")
    
    def save_result(self):
        """결과 저장"""
        result = self.result_text_widget.get(1.0, tk.END).strip()
        if not result:
            messagebox.showwarning("경고", "저장할 내용이 없습니다.")
            return
        
        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("텍스트 파일", "*.txt"), ("모든 파일", "*.*")]
        )
        
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(result)
                self.update_status(f"결과를 저장했습니다: {os.path.basename(filename)}")
            except Exception as e:
                messagebox.showerror("저장 오류", str(e))
    
    def update_status(self, message: str):
        """상태 메시지 업데이트"""
        self.status_label.config(text=message)
    
    def load_business_info_file(self):
        """업체정보 파일 로드"""
        filename = filedialog.askopenfilename(
            title="업체정보 파일 선택",
            filetypes=[("텍스트 파일", "*.txt"), ("모든 파일", "*.*")]
        )
        
        if filename:
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # 파싱
                self.parse_business_info(content)
                self.update_status(f"업체정보를 불러왔습니다: {os.path.basename(filename)}")
                
            except Exception as e:
                messagebox.showerror("오류", f"파일을 읽을 수 없습니다: {str(e)}")
    
    def parse_business_info(self, content: str):
        """업체정보 텍스트 파싱"""
        lines = content.split('\n')
        current_section = ""
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # 섹션 헤더 찾기
            if line.startswith('**') and line.endswith('**'):
                current_section = line.strip('*').strip(':').strip()
                continue
            
            # 각 섹션별 처리
            if current_section == "업체명":
                self.name_var.set(line)
                # 약칭 자동 생성
                if not self.short_name_var.get():
                    self.short_name_var.set(generate_short_name(line))
                    
            elif current_section == "SEO 키워드":
                self.seo_var.set(line)
                
            elif current_section == "주소":
                # 첫 번째 줄만 주소로 사용
                if not self.address_var.get():
                    self.address_var.set(line.split('-')[0].strip())
                    
            elif current_section == "운영시간":
                current_hours = self.hours_var.get()
                if current_hours:
                    self.hours_var.set(current_hours + ", " + line)
                else:
                    self.hours_var.set(line)
                    
            elif current_section == "전화번호":
                self.phone_var.set(line)
                
            elif current_section == "전체메뉴" or current_section == "대표메뉴":
                # 메뉴 파싱 (형식: - 메뉴명 가격)
                if line.startswith('-'):
                    menu_text = line[1:].strip()
                    # 가격 찾기 (숫자+원 패턴)
                    import re
                    price_match = re.search(r'(\d+,?\d*원)', menu_text)
                    if price_match:
                        price = price_match.group(1)
                        name = menu_text[:price_match.start()].strip()
                        
                        current_menu = self.menu_text.get(1.0, tk.END).strip()
                        if current_menu:
                            self.menu_text.insert(tk.END, f"\n{name}:{price}")
                        else:
                            self.menu_text.insert(1.0, f"{name}:{price}")
            
            elif current_section == "식사메뉴":
                # 식사 메뉴 파싱
                if line.startswith('-'):
                    menu_text = line[1:].strip()
                    # 가격 찾기 (숫자+원 패턴)
                    import re
                    price_match = re.search(r'(\d+,?\d*원)', menu_text)
                    if price_match:
                        price = price_match.group(1)
                        name = menu_text[:price_match.start()].strip()
                        
                        current_menu = self.ordered_menu_text.get(1.0, tk.END).strip()
                        if current_menu:
                            self.ordered_menu_text.insert(tk.END, f"\n{name}:{price}")
                        else:
                            self.ordered_menu_text.insert(1.0, f"{name}:{price}")
                            
            elif current_section == "분위기":
                self.atmosphere_var.set(line)
                
            elif current_section == "타겟 고객":
                self.target_customer_var.set(line)
                
            elif current_section == "주차정보":
                current_parking = self.parking_text.get(1.0, tk.END).strip()
                if current_parking:
                    self.parking_text.insert(tk.END, f"\n{line}")
                else:
                    self.parking_text.insert(1.0, line)
                    
            elif current_section == "주요특징":
                if line.startswith('-'):
                    feature = line[1:].strip()
                    current_features = self.features_text.get(1.0, tk.END).strip()
                    if current_features:
                        self.features_text.insert(tk.END, f"\n{feature}")
                    else:
                        self.features_text.insert(1.0, feature)
    
    def run(self):
        """GUI 실행"""
        self.root.mainloop()


# ===== 메인 실행 =====
if __name__ == "__main__":
    app = BlogConverterGUI()
    app.run()