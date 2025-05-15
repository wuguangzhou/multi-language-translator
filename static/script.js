// 页面加载时恢复保存的内容
window.onload = function() {
    // 清除之前的状态
    localStorage.removeItem('sourceText');
    localStorage.removeItem('translatedText');
    localStorage.removeItem('targetLanguage');

    // 其他恢复逻辑
    const savedSourceText = localStorage.getItem('sourceText');
    const savedTranslatedText = localStorage.getItem('translatedText');
    const savedTargetLanguage = localStorage.getItem('targetLanguage');
    
    if (savedSourceText) {
        document.getElementById('sourceText').value = savedSourceText;
    }
    if (savedTranslatedText) {
        document.getElementById('translatedText').value = savedTranslatedText;
    }
    if (savedTargetLanguage) {
        document.getElementById('targetLanguage').value = savedTargetLanguage;
    }

    // 恢复保存的主题
    applyTheme();

    // 添加翻译结果文本框的输入事件监听
    document.getElementById('translatedText').addEventListener('input', function() {
        localStorage.setItem('translatedText', this.value);
    });

    // 添加语言选择变化事件监听
    document.getElementById('targetLanguage').addEventListener('change', function() {
        localStorage.setItem('targetLanguage', this.value);
    });

    // 添加 Enter 键监听
    document.getElementById('sourceText').addEventListener('keypress', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault(); // 阻止默认的换行行为
            translateText();
        }
    });
}

// 应用保存的主题
function applyTheme() {
    const savedTheme = localStorage.getItem('theme') || 'harajuku';
    const root = document.documentElement;
    
    // 移除所有主题类
    root.classList.remove('pixel-theme', 'cyberpunk-theme');
    
    // 应用保存的主题
    if (savedTheme === 'pixel') {
        root.classList.add('pixel-theme');
    } else if (savedTheme === 'cyberpunk') {
        root.classList.add('cyberpunk-theme');
    }
    
    // 更新主题选项的选中状态
    const themeOptions = document.querySelectorAll('.theme-option');
    themeOptions.forEach(option => {
        if (option.dataset.theme === savedTheme) {
            option.classList.add('active');
        } else {
            option.classList.remove('active');
        }
    });
}

function translateText() {
    const sourceText = document.getElementById('sourceText').value.trim();
    if (!sourceText) {
        alert('请输入要翻译的文本');
        return;
    }

    // 保存源文本到本地存储
    localStorage.setItem('sourceText', sourceText);

    // 获取目标语言
    const targetLang = document.getElementById('targetLanguage').value;

    fetch('/translate', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            text: sourceText,
            target_lang: targetLang,
            source_lang: sourceLang
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            document.getElementById('translatedText').value = data.translated_text;
            // 保存翻译结果到本地存储
            localStorage.setItem('translatedText', data.translated_text);
        } else {
            alert('翻译失败：' + data.error);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('翻译请求失败，请稍后重试');
    });
}

document.addEventListener('DOMContentLoaded', function() {
    const sourceText = document.getElementById('sourceText');
    const translatedText = document.getElementById('translatedText');
    const status = document.getElementById('status');
    const loadingSpinner = document.getElementById('loadingSpinner');
    const clearBtn = document.getElementById('clearBtn');
    const copyBtn = document.getElementById('copyBtn');
    const copyTranslatedBtn = document.getElementById('copyTranslatedBtn');
    const speakBtn = document.getElementById('speakBtn');
    const historyList = document.getElementById('historyList');
    const title = document.querySelector('.title');
    const subtitle = document.querySelector('.subtitle');
    const langButtons = document.querySelectorAll('.lang-btn');
    const themeToggle = document.getElementById('themeToggle');
    const themeMenu = document.getElementById('themeMenu');
    const themeOptions = document.querySelectorAll('.theme-option');

    let sourceLang = 'zh';
    let targetLang = 'en';
    let isSpeaking = false;
    let speechSynthesis = window.speechSynthesis;
    let currentUtterance = null;
    let isThemeMenuOpen = false;

    // 主题菜单显示/隐藏功能
    themeToggle.addEventListener('click', function(e) {
        e.stopPropagation();
        
        if (isThemeMenuOpen) {
            themeMenu.classList.remove('active');
        } else {
            themeMenu.classList.add('active');
        }
        
        isThemeMenuOpen = !isThemeMenuOpen;
    });
    
    // 点击文档其他地方关闭主题菜单
    document.addEventListener('click', function() {
        if (isThemeMenuOpen) {
            themeMenu.classList.remove('active');
            isThemeMenuOpen = false;
        }
    });
    
    // 阻止菜单内的点击事件冒泡到文档
    themeMenu.addEventListener('click', function(e) {
        e.stopPropagation();
    });

    // 主题选项点击事件
    themeOptions.forEach(option => {
        option.addEventListener('click', function() {
            const theme = this.dataset.theme;
            const root = document.documentElement;
            
            // 移除所有主题类
            root.classList.remove('pixel-theme', 'cyberpunk-theme');
            
            // 应用选择的主题
            if (theme === 'pixel') {
                root.classList.add('pixel-theme');
            } else if (theme === 'cyberpunk') {
                root.classList.add('cyberpunk-theme');
            }
            
            // 更新选中状态
            themeOptions.forEach(opt => opt.classList.remove('active'));
            this.classList.add('active');
            
            // 保存主题设置
            localStorage.setItem('theme', theme);
            
            // 关闭主题菜单
            themeMenu.classList.remove('active');
            isThemeMenuOpen = false;
        });
    });

    // 标题交互效果
    title.addEventListener('click', function() {
        this.classList.add('animate');
        setTimeout(() => {
            this.classList.remove('animate');
        }, 4000);
    });

    subtitle.addEventListener('mouseover', function() {
        this.classList.add('animate');
    });

    subtitle.addEventListener('mouseout', function() {
        this.classList.remove('animate');
    });

    // 从localStorage加载历史记录
    let translationHistory = JSON.parse(localStorage.getItem('translationHistory') || '[]');
    
    // 初始化显示历史记录
    renderHistory();

    // 语言按钮点击事件
    document.querySelectorAll('.input-section .lang-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            document.querySelectorAll('.input-section .lang-btn').forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            sourceLang = this.dataset.lang;
        });
    });

    document.querySelectorAll('.output-section .lang-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            document.querySelectorAll('.output-section .lang-btn').forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            targetLang = this.dataset.lang;
            translateText();
        });
    });

    // 输入文本变化时自动翻译
    let translateTimeout;
    sourceText.addEventListener('input', function() {
        clearTimeout(translateTimeout);
        translateTimeout = setTimeout(translateText, 500);
    });

    // 清空按钮
    clearBtn.addEventListener('click', function() {
        sourceText.value = '';
        translatedText.value = '';
        status.textContent = '';
    });

    // 复制按钮
    copyBtn.addEventListener('click', function() {
        copyToClipboard(sourceText.value);
        showStatus('原文已复制到剪贴板');
    });

    copyTranslatedBtn.addEventListener('click', function() {
        copyToClipboard(translatedText.value);
        showStatus('译文已复制到剪贴板');
    });

    // 朗读功能
    speakBtn.addEventListener('click', function() {
        if (isSpeaking) {
            stopSpeaking();
        } else {
            startSpeaking();
        }
    });

    function startSpeaking() {
        const text = translatedText.value.trim();
        if (!text) return;

        // 如果已经在朗读，先停止
        if (currentUtterance) {
            speechSynthesis.cancel();
        }

        const utterance = new SpeechSynthesisUtterance(text);
        
        // 根据目标语言设置朗读语言
        const langMap = {
            'zh': 'zh-CN',
            'en': 'en-US',
            'ja': 'ja-JP',
            'ko': 'ko-KR'
        };
        utterance.lang = langMap[targetLang] || 'en-US';

        // 获取可用的语音列表
        const voices = speechSynthesis.getVoices();
        
        // 为日语和韩语选择女声
        if (targetLang === 'ja' || targetLang === 'ko') {
            // 查找对应语言的女声
            const femaleVoice = voices.find(voice => 
                voice.lang.startsWith(langMap[targetLang]) && 
                voice.name.toLowerCase().includes('female')
            );
            
            // 如果找到女声就使用，否则使用该语言的第一个可用声音
            const languageVoice = voices.find(voice => 
                voice.lang.startsWith(langMap[targetLang])
            );
            
            utterance.voice = femaleVoice || languageVoice;
        }

        // 朗读结束时的处理
        utterance.onend = function() {
            isSpeaking = false;
            speakBtn.classList.remove('speaking');
            currentUtterance = null;
        };

        // 朗读错误时的处理
        utterance.onerror = function(event) {
            console.error('Speech synthesis error:', event);
            isSpeaking = false;
            speakBtn.classList.remove('speaking');
            currentUtterance = null;
            showStatus('朗读出错，请重试');
        };

        // 开始朗读
        currentUtterance = utterance;
        speechSynthesis.speak(utterance);
        isSpeaking = true;
        speakBtn.classList.add('speaking');
    }

    // 确保语音列表已加载
    if (speechSynthesis.onvoiceschanged !== undefined) {
        speechSynthesis.onvoiceschanged = function() {
            // 语音列表已加载完成
            console.log('Voices loaded:', speechSynthesis.getVoices().length);
        };
    }

    function stopSpeaking() {
        if (speechSynthesis && isSpeaking) {
            speechSynthesis.cancel();
            isSpeaking = false;
            speakBtn.classList.remove('speaking');
            currentUtterance = null;
        }
    }

    // 页面卸载时停止朗读
    window.addEventListener('beforeunload', function() {
        stopSpeaking();
    });

    // 翻译函数
    function translateText() {
        const text = sourceText.value.trim();
        if (!text) {
            translatedText.value = '';
            return;
        }

        showLoading();
        fetch('/translate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                text: text,
                target_lang: targetLang,
                source_lang: sourceLang
            })
        })
        .then(response => response.json())
        .then(data => {
            hideLoading();
            if (data.success) {
                translatedText.value = data.translated_text;
                showStatus('翻译完成');
                
                // 添加到历史记录
                addToHistory({
                    sourceText: text,
                    translatedText: data.translated_text,
                    sourceLang: data.source_lang,
                    targetLang: data.target_lang,
                    timestamp: new Date().toLocaleString()
                });
            } else {
                showStatus(data.error || '翻译失败，请重试');
            }
        })
        .catch(error => {
            hideLoading();
            showStatus('网络错误，请检查网络连接');
            console.error('Error:', error);
        });
    }

    // 添加到历史记录
    function addToHistory(record) {
        translationHistory.unshift(record); // 添加到开头
        if (translationHistory.length > 10) {
            translationHistory.pop(); // 删除最后一条
        }
        localStorage.setItem('translationHistory', JSON.stringify(translationHistory));
        renderHistory();
    }

    // 渲染历史记录
    function renderHistory() {
        historyList.innerHTML = translationHistory.map(record => `
            <div class="history-item">
                <div class="history-text">${record.sourceText}</div>
                <div class="history-translation">${record.translatedText}</div>
                <div class="history-meta">
                    ${record.sourceLang} → ${record.targetLang} | ${record.timestamp}
                </div>
            </div>
        `).join('');
    }

    // 辅助函数
    function showLoading() {
        loadingSpinner.style.display = 'block';
        status.textContent = '正在翻译...';
    }

    function hideLoading() {
        loadingSpinner.style.display = 'none';
    }

    function showStatus(message) {
        status.textContent = message;
        setTimeout(() => {
            status.textContent = '';
        }, 3000);
    }

    function copyToClipboard(text) {
        navigator.clipboard.writeText(text).catch(err => {
            console.error('复制失败:', err);
            showStatus('复制失败，请手动复制');
        });
    }
}); 