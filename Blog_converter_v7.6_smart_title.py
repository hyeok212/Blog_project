"""
블로그 변환 프로그램 v7.6 - 스마트 제목 + 필수 항목 기능
v7.5 기반으로 특징 선택 기능 강화
- 업체명 약칭 자동 생성
- OpenAI API로 다양한 제목 생성
- [필수] 항목 기능 추가 (핵심 특징 보장)
- 특징 15-25개 권장
"""

import os
import re
import json
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
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
    
    # 특징 개수 권장값 (GUI 표시용)
    FEATURE_RECOMMENDED_MIN: int = 15   # 권장 최소 개수
    FEATURE_RECOMMENDED_MAX: int = 25   # 권장 최대 개수


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


# ===== 약칭 생성기 (v7.5 신규) =====
def generate_short_name(full_name: str) -> str:
    """업체명에서 제목용 약칭 자동 생성"""
    
    # 1. 지점명 제거
    branch_patterns = ['점', '호점', '역점', '점포', '매장', '지점', 'DT점']
    for pattern in branch_patterns:
        if pattern in full_name:
            # 마지막 패턴 이전까지만 사용
            parts = full_name.split(pattern)
            if len(parts) > 1:
                full_name = parts[0].strip()
    
    # 2. 프랜차이즈 패턴 처리
    franchise_patterns = {
        '스타벅스': '스타벅스',
        '맥도날드': '맥도날드',
        '버거킹': '버거킹',
        '이디야': '이디야',
        '투썸플레이스': '투썸',
        '파리바게뜨': '파바',
        '뚜레쥬르': '뚜레쥬르'
    }
    
    for franchise, short in franchise_patterns.items():
        if franchise in full_name:
            return short
    
    # 3. 메뉴명이 포함된 경우 처리
    # "예향한정식 목포보리굴비" → "예향한정식"
    words = full_name.split()
    if len(words) > 2:
        # 첫 2단어만 사용
        candidate = ' '.join(words[:2])
        
        # 메뉴 관련 단어가 있으면 첫 단어만
        menu_keywords = ['굴비', '갈비', '삼겹살', '치킨', '피자', '커피', '베이커리', 
                        '국수', '칼국수', '냉면', '곰탕', '설렁탕', '해물', '회']
        for keyword in menu_keywords:
            if keyword in candidate:
                return words[0]
        
        return candidate
    
    # 4. 길이 체크
    if len(full_name) > 10:
        # 10자 넘으면 첫 단어만
        return full_name.split()[0]
    
    return full_name


# ===== 말투 분석기 =====
class StyleAnalyzer:
    """블로그 말투 분석"""
    
    def analyze(self, text: str) -> StyleAnalysis:
        """텍스트에서 말투 특징 추출"""
        analysis = StyleAnalysis()
        
        # 종결어미 추출
        self._extract_endings(text, analysis)
        
        # 특징적 표현 추출
        self._extract_expressions(text, analysis)
        
        # 감정 표현 추출
        self._extract_emotions(text, analysis)
        
        # 문장 패턴 분석
        self._analyze_sentence_patterns(text, analysis)
        
        # 마커 분석
        self._analyze_markers(text, analysis)
        
        return analysis
    
    def _extract_endings(self, text: str, analysis: StyleAnalysis):
        """종결어미 추출"""
        # 문장 끝 패턴
        sentences = re.split(r'[.!?]\s*', text)
        endings = []
        
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) > 5:
                # 마지막 2-4글자 추출
                ending = sentence[-4:].strip()
                if ending and not any(char in ending for char in ['(', ')', '[', ']', '​']):
                    endings.append(ending)
        
        # 빈도 계산
        from collections import Counter
        ending_counts = Counter(endings)
        
        # 상위 15개 저장
        analysis.endings = [ending for ending, _ in ending_counts.most_common(15)]
    
    def _extract_expressions(self, text: str, analysis: StyleAnalysis):
        """특징적 표현 추출"""
        # 자주 사용되는 패턴
        patterns = [
            r'\w+해서\s+\w+',  # ~해서 ~
            r'\w+하고\s+\w+',  # ~하고 ~
            r'\w+으니까?\s+\w+',  # ~으니까 ~
            r'\w+어도\s+\w+',  # ~어도 ~
            r'정말\s+\w+',  # 정말 ~
            r'너무\s+\w+',  # 너무 ~
            r'\w+더라구요',  # ~더라구요
            r'\w+네요',  # ~네요
            r'\w+어요',  # ~어요
        ]
        
        expressions = []
        for pattern in patterns:
            matches = re.findall(pattern, text)
            expressions.extend(matches[:5])  # 각 패턴당 최대 5개
        
        # 중복 제거
        analysis.expressions = list(dict.fromkeys(expressions))
    
    def _extract_emotions(self, text: str, analysis: StyleAnalysis):
        """감정 표현 추출"""
        emotion_patterns = [
            r'만족\w*', r'감동\w*', r'좋\w*', r'맛있\w*', 
            r'최고\w*', r'추천\w*', r'인상\s*깊\w*', r'끝내\w*',
            r'훌륭\w*', r'즐겁\w*', r'행복\w*', r'놀라\w*',
            r'신선\w*', r'푸짐\w*', r'든든\w*', r'뿌듯\w*'
        ]
        
        emotions = []
        for pattern in emotion_patterns:
            matches = re.findall(pattern, text)
            emotions.extend(matches)
        
        # 중복 제거하고 빈도순 정렬
        from collections import Counter
        emotion_counts = Counter(emotions)
        analysis.emotions = [emotion for emotion, _ in emotion_counts.most_common(10)]
    
    def _analyze_sentence_patterns(self, text: str, analysis: StyleAnalysis):
        """문장 패턴 분석"""
        lines = text.split('\n')
        patterns = []
        
        # 문장 시작 패턴
        starters = []
        for line in lines:
            line = line.strip()
            if len(line) > 10:
                # 첫 5-7글자
                starter = line[:7].strip()
                if starter and not any(char in starter for char in ['(', ')', '[', ']', '​']):
                    starters.append(starter)
        
        # 자주 사용되는 시작 패턴
        from collections import Counter
        starter_counts = Counter(starters)
        common_starters = [s for s, count in starter_counts.most_common(5) if count > 1]
        
        if common_starters:
            patterns.append(f"자주 시작하는 패턴: {', '.join(common_starters)}")
        
        # 문장 길이 분석
        sentence_lengths = [len(s.strip()) for s in re.split(r'[.!?]', text) if s.strip()]
        if sentence_lengths:
            avg_length = sum(sentence_lengths) // len(sentence_lengths)
            patterns.append(f"평균 문장 길이: 약 {avg_length}자")
        
        analysis.sentence_patterns = patterns
    
    def _analyze_markers(self, text: str, analysis: StyleAnalysis):
        """(지도), (동영상) 마커 분석"""
        lines = text.split('\n')
        marker_info = {
            'has_map': False,
            'has_video': False,
            'map_positions': [],
            'video_positions': []
        }
        
        for i, line in enumerate(lines):
            # (지도) 마커 찾기
            if '(지도)' in line:
                marker_info['has_map'] = True
                # 전후 문맥 저장 (위치와 주변 내용)
                context = lines[max(0, i-1):min(len(lines), i+2)]
                marker_info['map_positions'].append({
                    'line_num': i,
                    'relative_position': i / len(lines),  # 상대 위치 (0~1)
                    'context': '\n'.join(context)
                })
            
            # (동영상) 마커 찾기
            if '(동영상)' in line:
                marker_info['has_video'] = True
                context = lines[max(0, i-1):min(len(lines), i+2)]
                marker_info['video_positions'].append({
                    'line_num': i,
                    'relative_position': i / len(lines),
                    'context': '\n'.join(context)
                })
        
        analysis.marker_info = marker_info


# ===== 특징 선택기 =====
class FeatureSelector:
    """특징 랜덤 선택기"""
    
    def __init__(self, min_count: int = 7, max_count: int = 8):
        self.min_count = min_count
        self.max_count = max_count
    
    def select_features(self, features: List[str], seed: Optional[int] = None) -> List[str]:
        """
        특징 리스트에서 선택
        [필수] 표시된 항목은 무조건 포함, 나머지에서 랜덤 선택
        """
        if not features:
            return []
        
        # 1. [필수] 항목과 선택 항목 분리
        required_features = []
        optional_features = []
        
        for feature in features:
            if feature.strip().startswith('[필수]'):
                # [필수] 태그 제거하고 추가
                cleaned_feature = feature.replace('[필수]', '').strip()
                required_features.append(cleaned_feature)
            else:
                optional_features.append(feature.strip())
        
        # 2. 필수 항목이 max_count를 초과하면 필수 항목만 반환
        if len(required_features) >= self.max_count:
            return required_features[:self.max_count]
        
        # 3. 전체 특징(필수+선택)이 min_count보다 적으면 모두 반환
        total_features = len(required_features) + len(optional_features)
        if total_features <= self.min_count:
            return required_features + optional_features
        
        # 4. 랜덤 시드 설정
        if seed is not None:
            random.seed(seed)
        
        # 5. 필수 항목 제외하고 선택할 개수 계산
        remaining_slots = random.randint(
            max(0, self.min_count - len(required_features)),
            self.max_count - len(required_features)
        )
        
        # 6. 선택 항목에서 랜덤 선택
        selected_optional = []
        if remaining_slots > 0 and optional_features:
            # 선택 가능한 개수보다 슬롯이 많으면 모든 선택 항목 사용
            if remaining_slots >= len(optional_features):
                selected_optional = optional_features
            else:
                selected_optional = random.sample(optional_features, remaining_slots)
        
        # 7. 필수 + 선택 조합하여 반환
        return required_features + selected_optional


# ===== 프롬프트 빌더 =====
class PromptBuilder:
    """효과적인 프롬프트 생성"""
    
    def __init__(self, feature_selector: Optional[FeatureSelector] = None):
        self.feature_selector = feature_selector or FeatureSelector()
    
    def build_conversion_prompt(self, original_text: str, style_analysis: StyleAnalysis, 
                               business_info: BusinessInfo, feature_seed: Optional[int] = None) -> str:
        """변환용 프롬프트 생성"""
        
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
        else:
            # 원본에 마커가 없는 경우
            prompt += """
9. 다음 위치에 (지도), (동영상) 마커를 포함하세요:
   - (지도) 마커: 주소나 위치 정보 언급 후 또는 전체의 약 80% 지점
   - (동영상) 마커: 메뉴나 분위기 설명 후 또는 전체의 약 60% 지점
   **중요: 정확히 (지도), (동영상) 형식으로만 작성하고, (지도삽입) 등의 변형은 사용하지 마세요**"""
        
        prompt += f"""

원본의 스타일을 완벽하게 모방하여 '{business_info.name}'을 소개하는 블로그를 작성하세요.
지역명은 '{location}'으로 통일하세요."""

        return prompt
    
    def build_title_prompt(self, keyword: str, business_info: BusinessInfo) -> str:
        """제목 생성용 프롬프트 생성 (v7.5 신규)"""
        
        # 사용할 업체명 (약칭 우선)
        name_to_use = business_info.short_name if business_info.short_name else business_info.name
        
        # 핵심 특징 1-2개 선택
        key_features = business_info.features[:2] if business_info.features else []
        
        # 대표 메뉴 1개 선택
        main_menu = ""
        if business_info.ordered_items:
            main_menu = business_info.ordered_items[0]['name']
        elif business_info.menu_items:
            main_menu = business_info.menu_items[0]['name']
        
        prompt = f"""블로그 제목을 생성해주세요.

정보:
- SEO 키워드: {keyword}
- 업체명: {name_to_use}
- 주요 특징: {', '.join(key_features) if key_features else '특별한 맛집'}
- 대표 메뉴: {main_menu if main_menu else '다양한 메뉴'}

요구사항:
1. 20-40자 이내로 작성
2. 키워드를 자연스럽게 포함
3. 업체명을 포함
4. 실제 방문 후기 느낌으로
5. 클릭하고 싶은 매력적인 제목
6. 제목 부호나 특수문자 사용하지 않기

예시:
- {keyword} {name_to_use}에서 든든한 한끼 식사
- {name_to_use} 방문기 {keyword} 추천
- {keyword} {name_to_use}의 {main_menu if main_menu else '특별한 메뉴'}

제목만 출력하세요:"""

        return prompt


# ===== 마커 처리기 =====
class MarkerProcessor:
    """변환 결과에 마커 추가"""
    
    def process(self, text: str, original_markers: Dict, business_info: BusinessInfo) -> str:
        """변환된 텍스트에 마커가 없으면 추가"""
        result = text
        
        # (지도) 마커가 결과에 없으면 추가 (원본 유무와 관계없이)
        # '(지도'로 시작하는 모든 변형 체크 (예: (지도), (지도삽입) 등)
        if '(지도' not in result:
            result = self._add_map_marker(result, original_markers, business_info)
        
        # (동영상) 마커가 결과에 없으면 추가 (원본 유무와 관계없이)
        # '(동영상'으로 시작하는 모든 변형 체크
        if '(동영상' not in result:
            result = self._add_video_marker(result, original_markers, business_info)
        
        return result
    
    def _add_map_marker(self, text: str, original_markers: Dict, business_info: BusinessInfo) -> str:
        """(지도) 마커 추가"""
        lines = text.split('\n')
        
        # 주소나 위치 정보가 있는 줄 찾기
        insert_position = -1
        for i, line in enumerate(lines):
            if any(keyword in line for keyword in ['위치', '주소', business_info.address[:10]]):
                # 현재 줄이 문장으로 끝나는지 확인
                stripped = line.strip()
                if stripped and stripped[-1] in '.!?다요죠':
                    # 문장이 끝났으면 바로 다음
                    insert_position = i + 1
                else:
                    # 문장이 안 끝났으면 다음 빈 줄 찾기
                    insert_position = i + 1
                    while insert_position < len(lines) and lines[insert_position].strip() != '':
                        insert_position += 1
                break
        
        # 못 찾았으면 맨 마지막에 추가 (빈 줄 제외)
        if insert_position == -1:
            # 맨 뒤에서부터 빈 줄이 아닌 곳 찾기
            insert_position = len(lines)
            while insert_position > 0 and lines[insert_position - 1].strip() == '':
                insert_position -= 1
        
        # 빈 줄 다음에 (지도) 삽입
        lines.insert(insert_position, '')
        lines.insert(insert_position + 1, '(지도)')
        lines.insert(insert_position + 2, '')
        
        return '\n'.join(lines)
    
    def _add_video_marker(self, text: str, original_markers: Dict, business_info: BusinessInfo) -> str:
        """(동영상) 마커 추가"""
        lines = text.split('\n')
        
        # 메뉴나 분위기 설명이 있는 줄 찾기
        insert_position = -1
        for i, line in enumerate(lines):
            if any(keyword in line for keyword in ['메뉴', '분위기', '인테리어', '맛있']):
                # 현재 줄이 문장으로 끝나는지 확인
                stripped = line.strip()
                if stripped and stripped[-1] in '.!?다요죠':
                    # 문장이 끝났으면 바로 다음
                    insert_position = i + 1
                else:
                    # 문장이 안 끝났으면 다음 빈 줄 찾기
                    insert_position = i + 1
                    while insert_position < len(lines) and lines[insert_position].strip() != '':
                        insert_position += 1
                break
        
        # 못 찾았으면 맨 마지막에 추가 (빈 줄 제외)
        if insert_position == -1:
            # 맨 뒤에서부터 빈 줄이 아닌 곳 찾기
            insert_position = len(lines)
            while insert_position > 0 and lines[insert_position - 1].strip() == '':
                insert_position -= 1
        
        # 빈 줄 다음에 (동영상) 삽입
        lines.insert(insert_position, '')
        lines.insert(insert_position + 1, '(동영상)')
        lines.insert(insert_position + 2, '')
        
        return '\n'.join(lines)


# ===== API 핸들러 =====
class OpenAIAPIHandler:
    """OpenAI API 호출 관리"""
    
    def __init__(self, config: Config):
        self.config = config
        self.client = OpenAI(api_key=config.API_KEY)
    
    def convert_blog(self, prompt: str) -> str:
        """블로그 변환 API 호출"""
        try:
            response = self.client.chat.completions.create(
                model=self.config.MODEL,
                max_tokens=self.config.MAX_TOKENS,
                temperature=self.config.TEMPERATURE,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            if "api_key" in str(e).lower() or "authentication" in str(e).lower():
                raise Exception("API 키가 유효하지 않습니다. 올바른 OpenAI API 키를 입력해주세요.")
            elif "model" in str(e).lower():
                raise Exception(f"모델 '{self.config.MODEL}'을 찾을 수 없습니다.")
            else:
                raise Exception(f"API 호출 오류: {str(e)}")
    
    def generate_title(self, prompt: str) -> str:
        """제목 생성 API 호출 (v7.5 신규)"""
        try:
            response = self.client.chat.completions.create(
                model=self.config.TITLE_MODEL,
                max_tokens=self.config.TITLE_MAX_TOKENS,
                temperature=self.config.TITLE_TEMPERATURE,
                messages=[{"role": "user", "content": prompt}],
                timeout=3.0  # 3초 타임아웃
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            # 에러 발생시 None 반환 (fallback 처리를 위해)
            print(f"제목 생성 API 오류: {str(e)}")
            return None


# ===== 메인 변환 엔진 =====
class BlogConverter:
    """블로그 변환 엔진"""
    
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
        import random
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
        self.root.title("블로그 변환 프로그램 v7.5 - 스마트 제목 생성")
        self.root.geometry("1300x900")
        
        # 설정
        self.config = Config()
        self.converter = None
        self.original_text = ""
        self.business_info = BusinessInfo()
        
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
            original_frame, width=40, height=40, wrap=tk.WORD, font=("맑은 고딕", 10)
        )
        self.original_text_widget.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        btn_frame1 = ttk.Frame(original_frame)
        btn_frame1.grid(row=1, column=0, pady=5)
        ttk.Button(btn_frame1, text="파일 열기", command=self.load_file).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame1, text="예시 로드", command=self.load_example).pack(side=tk.LEFT)
        
        # 2. 업체 정보 입력
        info_frame = ttk.LabelFrame(main_frame, text="업체 정보 입력", padding="10")
        info_frame.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5)
        
        # 입력 필드들
        row = 0
        
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
        self.seo_var = tk.StringVar()
        ttk.Entry(info_frame, textvariable=self.seo_var, width=35).grid(row=row, column=1, pady=5)
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
        
        # 특징 입력 프레임 (도움말 포함)
        features_frame = ttk.Frame(info_frame)
        features_frame.grid(row=row, column=1, pady=5, sticky=(tk.W, tk.E))
        
        self.features_text = tk.Text(features_frame, width=35, height=3)
        self.features_text.pack(side=tk.TOP)
        
        # 도움말 텍스트
        help_text = ("💡 특징 작성 가이드:\n"
                    "• 15-25개 작성 권장 (다양성 확보)\n" 
                    "• [필수] 표시: 항상 포함될 핵심 특징\n"
                    "  예) [필수] 14시간 우려낸 사골 육수\n"
                    "• 나머지는 랜덤 선택 (총 7-8개 사용)")
        
        help_label = ttk.Label(features_frame, text=help_text, 
                              font=("맑은 고딕", 8), foreground="gray")
        help_label.pack(side=tk.TOP, anchor=tk.W, pady=(2, 0))
        
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
            result_frame, width=40, height=40, wrap=tk.WORD, font=("맑은 고딕", 10)
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
    
    def load_example(self):
        """예시 파일 로드"""
        example_path = "/mnt/c/Users/혁/Desktop/예시.txt"
        if os.path.exists(example_path):
            try:
                with open(example_path, 'r', encoding='utf-8') as f:
                    self.original_text = f.read()
                    self.original_text_widget.delete(1.0, tk.END)
                    self.original_text_widget.insert(1.0, self.original_text)
                self.update_status("예시 파일을 불러왔습니다.")
            except Exception as e:
                messagebox.showerror("오류", f"예시 파일을 읽을 수 없습니다: {str(e)}")
        else:
            messagebox.showinfo("알림", "예시 파일이 없습니다.")
    
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
                # 약칭 자동 생성 (v7.5 신규)
                if not self.short_name_var.get():
                    short_name = generate_short_name(line)
                    self.short_name_var.set(short_name)
                
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