from flask import Flask, render_template, request, jsonify, session
import requests
import time
from functools import wraps
import re
import json
import random
import threading
import uuid
import os
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)
app.secret_key = os.urandom(24)  # 设置Flask session密钥

# 创建线程池
executor = ThreadPoolExecutor(max_workers=10)

# 每个用户会话的翻译历史记录
translation_history = {}
translation_history_lock = threading.RLock()

MYMEMORY_API_URL = "https://api.mymemory.translated.net/get"

def detect_language(text):
    """
    自动检测文本语言
    
    参数:
        text (str): 需要检测语言的文本
        
    返回:
        str: 检测到的语言代码 ('ja'=日语, 'zh'=中文, 'ko'=韩语, 'en'=英语)
        
    说明:
        使用正则表达式检测文本中的字符范围，根据不同语言的Unicode字符范围进行判断
        如果都不匹配，则默认返回英语
    """
    # 检测日文字符（平假名、片假名）
    if re.search(r'[\u3040-\u309F\u30A0-\u30FF]', text):
        return 'ja'
    # 检测中文字符
    elif re.search(r'[\u4e00-\u9fff]', text):
        return 'zh'
    # 检测韩文字符
    elif re.search(r'[\uac00-\ud7af]', text):
        return 'ko'
    else:
        return 'en'  # 默认英语

def retry_on_failure(max_retries=3, delay=1):
    """
    创建一个装饰器，用于自动重试可能失败的函数
    
    参数:
        max_retries (int): 最大重试次数，默认为3次
        delay (int): 重试间隔时间(秒)，默认为1秒
        
    返回:
        function: 装饰器函数
        
    说明:
        用于网络请求等不稳定操作的自动重试机制
        如果所有重试都失败，将抛出最后一次的异常
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    if attempt < max_retries - 1:
                        time.sleep(delay)
            raise last_error
        return wrapper
    return decorator

def split_text(text, max_length=450):
    """
    将长文本分割成较短的片段，以适应API的长度限制
    
    参数:
        text (str): 需要分割的原始文本
        max_length (int): 单个片段的最大长度，默认为450字符
        
    返回:
        list: 分割后的文本片段列表
        
    说明:
        优先按句号'。'分割，保持句子完整性
        如果单个句子超过长度限制，则按段落(\n)分割
        如果段落仍然过长，则按固定长度分割
    """
    if len(text) <= max_length:
        return [text]
    
    # 尝试在句子末尾分割
    sentences = text.split('。')
    segments = []
    current_segment = ''
    
    for sentence in sentences:
        # 如果一个句子本身就超过限制
        if len(sentence) > max_length:
            # 按照段落分割
            paragraphs = sentence.split('\n')
            for paragraph in paragraphs:
                if len(paragraph) > max_length:
                    # 如果段落仍然太长，按固定长度分割
                    for i in range(0, len(paragraph), max_length):
                        segments.append(paragraph[i:i + max_length])
                else:
                    segments.append(paragraph)
        else:
            # 尝试将句子添加到当前段
            if len(current_segment + sentence + '。') <= max_length:
                current_segment += sentence + '。'
            else:
                if current_segment:
                    segments.append(current_segment)
                current_segment = sentence + '。'
    
    if current_segment:
        segments.append(current_segment)
    
    return segments

@retry_on_failure(max_retries=3, delay=1)
def translate_segment(segment, source_lang, target_lang):
    """
    翻译单个文本片段
    
    参数:
        segment (str): 需要翻译的文本片段
        source_lang (str): 源语言代码
        target_lang (str): 目标语言代码
        
    返回:
        str: 翻译后的文本片段
    """
    params = {
        "q": segment,
        "langpair": f"{source_lang}|{target_lang}"
    }
    response = requests.get(MYMEMORY_API_URL, params=params, timeout=10)
    result = response.json()
    
    if 'responseStatus' in result and result['responseStatus'] == 200:
        return result['responseData']['translatedText']
    else:
        raise Exception(result.get('responseDetails', 'Unknown error'))

def get_session_id():
    """
    获取或创建用户会话ID
    
    返回:
        str: 用户会话ID
    """
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    return session['session_id']

def save_translation_history(session_id, original_text, translated_text, source_lang, target_lang):
    """
    保存翻译历史记录
    
    参数:
        session_id (str): 用户会话ID
        original_text (str): 原始文本
        translated_text (str): 翻译后的文本
        source_lang (str): 源语言代码
        target_lang (str): 目标语言代码
    """
    with translation_history_lock:
        if session_id not in translation_history:
            translation_history[session_id] = []
        
        # 限制历史记录数量，只保留最新的10条
        if len(translation_history[session_id]) >= 10:
            translation_history[session_id].pop(0)
        
        translation_history[session_id].append({
            'original_text': original_text,
            'translated_text': translated_text,
            'source_lang': source_lang,
            'target_lang': target_lang,
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
        })

def translate_text_async(text, target_lang, source_lang=None):
    """
    异步翻译文本到目标语言
    
    参数:
        text (str): 需要翻译的文本
        target_lang (str): 目标语言代码
        source_lang (str, 可选): 源语言代码，不提供则自动检测
        
    返回:
        str: 翻译后的文本
        
    说明:
        使用多线程并发翻译多个文本片段
        支持自动检测源语言或使用用户指定的源语言
        如果源语言和目标语言相同，则直接返回原文
    """
    # 如果用户没有选择源语言，才使用自动检测
    if not source_lang:
        source_lang = detect_language(text)
    
    # 如果源语言和目标语言相同，直接返回原文
    if source_lang == target_lang:
        return text

    # 分段翻译
    segments = split_text(text)
    
    # 使用线程池并发翻译
    futures = []
    for segment in segments:
        future = executor.submit(translate_segment, segment, source_lang, target_lang)
        futures.append(future)
    
    # 获取所有翻译结果
    translated_segments = []
    for future in futures:
        try:
            translated_segments.append(future.result())
        except Exception as e:
            # 如果单个片段翻译失败，记录错误但继续尝试其他片段
            print(f"翻译片段失败: {str(e)}")
            raise e
    
    # 合并翻译结果
    return ' '.join(translated_segments)

@app.route('/')
def index():
    """
    渲染主页面
    
    返回:
        HTML: 渲染后的index.html模板
    """
    return render_template('index.html')

@app.route('/translate', methods=['POST'])
def translate():
    """
    处理翻译请求的API端点
    
    请求参数(JSON):
        text (str): 需要翻译的文本
        target_lang (str): 目标语言代码
        source_lang (str, 可选): 源语言代码，不提供则自动检测
        
    返回:
        JSON: 包含翻译结果或错误信息
            success (bool): 是否成功
            translated_text (str): 翻译后的文本 (成功时)
            source_lang (str): 源语言代码 (成功时)
            target_lang (str): 目标语言代码 (成功时)
            error (str): 错误信息 (失败时)
    """
    try:
        # 获取会话ID
        session_id = get_session_id()
        
        data = request.get_json()
        text = data.get('text', '')
        target_lang = data.get('target_lang', 'en')
        source_lang = data.get('source_lang', None)  # 获取用户选择的源语言

        if not text.strip():
            return jsonify({
                'success': False,
                'error': '请输入要翻译的文本'
            }), 400

        # 统一目标语言代码
        lang_map = {
            'en': 'en',
            'zh': 'zh',
            'zh-CN': 'zh',
            'zh-cn': 'zh',
            'ja': 'ja',
            'ko': 'ko'
        }
        target_lang = lang_map.get(target_lang, 'en')
        if source_lang:
            source_lang = lang_map.get(source_lang, source_lang)

        try:
            # 使用异步翻译函数
            translated_text = translate_text_async(text, target_lang, source_lang)
            
            # 保存翻译历史
            actual_source_lang = source_lang if source_lang else detect_language(text)
            save_translation_history(session_id, text, translated_text, actual_source_lang, target_lang)
            
        except Exception as e:
            error_msg = str(e)
            if "QUERY LENGTH LIMIT EXCEEDED" in error_msg:
                error_msg = "文本过长，已自动分段翻译"
            return jsonify({
                'success': False,
                'error': f'翻译服务暂时不可用，请稍后重试。错误信息：{error_msg}'
            }), 500

        return jsonify({
            'success': True,
            'translated_text': translated_text,
            'source_lang': source_lang if source_lang else detect_language(text),
            'target_lang': target_lang
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'发生错误：{str(e)}'
        }), 500

@app.route('/translation_history', methods=['GET'])
def get_translation_history():
    """
    获取当前会话的翻译历史记录
    
    返回:
        JSON: 包含历史记录或错误信息
            success (bool): 是否成功
            history (list): 历史记录列表 (成功时)
            error (str): 错误信息 (失败时)
    """
    try:
        session_id = get_session_id()
        with translation_history_lock:
            history = translation_history.get(session_id, [])
        return jsonify({
            'success': True,
            'history': history
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'获取历史记录失败：{str(e)}'
        }), 500

@app.route('/vocabulary')
def vocabulary():
    """
    渲染词汇表页面
    
    返回:
        HTML: 渲染后的vocabulary.html模板
    """
    return render_template('vocabulary.html')

@app.route('/get_words')
def get_words():
    """
    获取所有词汇表单词的API端点
    
    返回:
        JSON: 包含所有单词的列表或错误信息
            words (list): 单词对象列表 (成功时)
                word (str): 单词
                translation (str): 翻译
            error (str): 错误信息 (失败时)
            
    说明:
        从两个词库文件(wordbank.json和wordbank_new.json)读取单词
        合并为一个列表并去除完全重复的单词(包括大小写)
    """
    try:
        with open('static/wordbank.json', 'r', encoding='utf-8') as f1:
            data1 = json.load(f1)
        with open('static/wordbank_new.json', 'r', encoding='utf-8') as f2:
            data2 = json.load(f2)
        
        # 保留所有单词，包括只有大小写不同的版本
        all_words = []
        
        # 将两个词库中的所有单词添加到列表中
        all_words.extend(data1['words'])
        all_words.extend(data2['words'])
        
        # 创建一个用于检查完全相同单词的集合
        # 这里完全相同意味着包括大小写在内都相同
        exact_words = set()
        unique_words = []
        
        for word in all_words:
            # 使用单词的原始大小写作为唯一标识
            word_key = word['word']  
            
            # 如果这个完全相同的单词（包括大小写）不在集合中，则添加它
            if word_key not in exact_words:
                exact_words.add(word_key)
                unique_words.append(word)
        
        return jsonify({'words': unique_words})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/search_words')
def search_words():
    """
    搜索词汇表单词的API端点
    
    请求参数(GET):
        term (str): 搜索关键词
        case_sensitive (str): 是否区分大小写('true'或'false')
        
    返回:
        JSON: 包含匹配的单词列表或错误信息
            words (list): 匹配的单词对象列表 (成功时)
                word (str): 单词
                translation (str): 翻译
            error (str): 错误信息 (失败时)
            
    说明:
        从两个词库文件读取单词
        根据搜索关键词匹配单词或翻译
        支持区分大小写和不区分大小写的搜索
        如果没有提供搜索关键词，返回所有单词
    """
    try:
        search_term = request.args.get('term', '')
        case_sensitive = request.args.get('case_sensitive', 'false').lower() == 'true'
        
        with open('static/wordbank.json', 'r', encoding='utf-8') as f1:
            data1 = json.load(f1)
        with open('static/wordbank_new.json', 'r', encoding='utf-8') as f2:
            data2 = json.load(f2)
        all_words = data1['words'] + data2['words']
        
        if not search_term:
            return jsonify({'words': all_words})
            
        filtered_words = []
        for word in all_words:
            # 检查单词
            word_match = False
            if case_sensitive:
                word_match = search_term in word['word']
            else:
                word_match = search_term.lower() in word['word'].lower()
                
            # 检查翻译
            translation_match = False
            if case_sensitive:
                translation_match = search_term in word['translation']
            else:
                translation_match = search_term.lower() in word['translation'].lower()
                
            # 如果单词或翻译匹配，则添加到结果中
            if word_match or translation_match:
                filtered_words.append(word)
                
        return jsonify({'words': filtered_words})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/get_pronunciation')
def get_pronunciation():
    """
    获取单词发音的API端点(代理请求避免跨域问题)
    
    请求参数(GET):
        word (str): 需要获取发音的单词
        
    返回:
        audio: MP3格式的音频数据 (成功时)
        JSON: 错误信息 (失败时)
            success (bool): 是否成功
            error (str): 错误信息
            
    说明:
        使用Google Text-to-Speech API获取单词的英语发音
        作为代理服务器转发请求，解决前端跨域限制
        返回音频二进制数据，而不是JSON响应
    """
    try:
        word = request.args.get('word', '').strip()
        if not word:
            return jsonify({'success': False, 'error': '单词不能为空'}), 400
            
        # 使用Flask作为代理请求Google Text-to-Speech API
        tts_url = f"https://translate.google.com/translate_tts?ie=UTF-8&q={word}&tl=en&client=tw-ob"
        
        try:
            # 直接请求音频并返回给客户端
            audio_response = requests.get(tts_url, 
                                    headers={
                                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                                        'Referer': 'https://translate.google.com/'
                                    },
                                    timeout=5)
            
            if audio_response.status_code == 200:
                # 返回二进制音频数据，注意这里不是JSON
                from flask import Response
                return Response(
                    audio_response.content, 
                    mimetype="audio/mpeg",
                    headers={
                        "Content-Disposition": f"inline; filename={word}.mp3"
                    }
                )
            else:
                return jsonify({
                    'success': False, 
                    'error': f'获取音频失败: {audio_response.status_code}'
                }), 500
                
        except Exception as req_error:
            return jsonify({
                'success': False, 
                'error': f'请求发音服务失败: {str(req_error)}'
            }), 500
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/add_word', methods=['POST'])
def add_word():
    """
    添加新单词到词汇表的API端点
    
    请求参数(JSON):
        word (str): 要添加的单词
        translation (str): 单词的翻译
        
    返回:
        JSON: 包含操作结果
            success (bool): 是否成功
            message (str): 成功信息 (成功时)
            word (object): 添加的单词对象 (成功时)
                word (str): 单词
                translation (str): 翻译
            error (str): 错误信息 (失败时)
            
    说明:
        将新单词添加到wordbank_new.json文件中
        如果单词已存在(完全相同，包括大小写)，则更新其翻译
        如果翻译中没有词性，默认添加'n.'(名词)前缀
        如果词库文件不存在或格式错误，会创建新的词库结构
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': '请求数据不能为空'}), 400
            
        word = data.get('word', '').strip()  # 保留原始大小写
        translation = data.get('translation', '').strip()
        
        if not word:
            return jsonify({'success': False, 'error': '单词不能为空'}), 400
        if not translation:
            return jsonify({'success': False, 'error': '翻译不能为空'}), 400
            
        # 使用统一的词性格式，如果没有指定词性，默认为n.（名词）
        if '.' not in translation:
            translation = 'n.' + translation
            
        # 读取现有单词库
        try:
            with open('static/wordbank_new.json', 'r', encoding='utf-8') as f:
                wordbank = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            # 如果文件不存在或格式错误，创建新的单词库结构
            wordbank = {"words": []}
            
        # 检查单词是否已存在（完全相同，包括大小写）
        exists = False
        for existing_word in wordbank["words"]:
            if existing_word["word"] == word:  # 注意这里改为严格相等
                exists = True
                # 更新现有单词的翻译
                existing_word["translation"] = translation
                break
                
        # 如果单词不存在，添加到单词库
        if not exists:
            wordbank["words"].append({
                "word": word,  # 保留原始大小写
                "translation": translation
            })
            
        # 将更新后的单词库写回文件
        with open('static/wordbank_new.json', 'w', encoding='utf-8') as f:
            json.dump(wordbank, f, ensure_ascii=False, indent=2)
            
        return jsonify({
            'success': True,
            'message': '单词已成功添加到单词库',
            'word': {
                'word': word,
                'translation': translation
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)