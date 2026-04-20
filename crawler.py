# =================================================
# 1. 모든 도구(라이브러리) 불러오기
# =================================================
import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import ssl
import os
import datetime

# =================================================
# 2. 데이터 추출 (Crawling)
# =================================================
print("방송통신위원회 크롤링을 시작합니다...")

# 크롤링할 게시판 목록 (게시판 이름, URL)
# ※ URL은 실제 게시판 주소로 확인 후 수정이 필요할 수 있습니다.
target_pages = {
    "의사일정/회의록/속기록": "https://kcc.go.kr/user.do?page=A02030100",
    "심결정보": "https://kcc.go.kr/user.do?page=A02030300",
    "입법예고": "https://kcc.go.kr/user.do?page=A02020200",
    "공지사항": "https://kcc.go.kr/user.do?page=A05030000",
    "보도자료": "https://kcc.go.kr/user.do?page=A05020000",
    "인사": "https://kcc.go.kr/user.do?page=A05040000"
}

# 최종 결과를 담을 리스트
crawled_results = []

# 각 게시판을 순회하며 크롤링
for board_name, board_url in target_pages.items():
    try:
        response = requests.get(board_url, headers={'User-Agent': 'Mozilla/5.0'})
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # ※ 중요: 'table.board-list-table > tbody > tr' 부분은 실제 홈페이지의 HTML 구조에 따라
            #    웹브라우저의 '개발자 도구(F12)'로 확인 후 수정해야 할 수 있습니다.
            posts = soup.select('table.board-list-table > tbody > tr')

            # 게시글이 없는 경우 건너뛰기
            if not posts:
                print(f"[{board_name}] 게시판에서 게시글 목록을 찾지 못했습니다.")
                continue

            for post in posts:
                # 공지용 게시글(보통 class가 notice)은 건너뛰는 경우가 많습니다.
                if 'notice' in post.get('class', []):
                    continue

                title_element = post.select_one('td.title > a')
                # 날짜 태그는 td 리스트 중 특정 순서에 있을 수 있습니다 (예: 4번째)
                date_element = post.select_one('td:nth-of-type(4)') 
                
                if title_element and date_element:
                    title = title_element.get_text(strip=True)
                    # 상대 경로일 경우, 전체 URL로 만들어줍니다.
                    link = title_element['href']
                    if not link.startswith('http'):
                        link = 'https://kcc.go.kr' + link

                    date = date_element.get_text(strip=True)

                    crawled_results.append({
                        "게시판": board_name,
                        "제목": title,
                        "날짜": date,
                        "링크": link
                    })
        else:
            print(f"[{board_name}] 페이지를 열 수 없습니다. (상태 코드: {response.status_code})")
    except Exception as e:
        print(f"[{board_name}] 크롤링 중 오류 발생: {e}")

print(f"--- 크롤링 완료 ---")
print(f"총 {len(crawled_results)}개의 소식을 찾았습니다.")

# =================================================
# 3. 이메일 생성 및 발송
# =================================================
if crawled_results:
    # --- GitHub Secrets에 저장된 민감 정보 가져오기 ---
    SENDER_EMAIL = os.environ.get('SENDER_EMAIL')
    SENDER_PASSWORD = os.environ.get('SENDER_PASSWORD')
    RECEIVER_EMAIL = os.environ.get('RECEIVER_EMAIL')

    if not all([SENDER_EMAIL, SENDER_PASSWORD, RECEIVER_EMAIL]):
        print("이메일 발송에 필요한 정보(Secret)가 설정되지 않았습니다.")
    else:
        # 이메일 본문을 HTML 테이블 형태로 만드는 함수
        def create_email_body(results):
            today = datetime.date.today().strftime("%Y-%m-%d")
            html = f"""
            <html>
              <head>
                <style>
                  body {{ font-family: sans-serif; }}
                  table {{ width: 100%; border-collapse: collapse; }}
                  th, td {{ border: 1px solid #dddddd; text-align: left; padding: 8px; }}
                  th {{ background-color: #f2f2f2; }}
                  a {{ color: #0066cc; text-decoration: none; }}
                  a:hover {{ text-decoration: underline; }}
                </style>
              </head>
              <body>
                <h2>방송통신위원회 최신 게시글 알림 ({today})</h2>
                <table>
                  <tr>
                    <th style="width:20%;">게시판</th>
                    <th>제목</th>
                    <th style="width:15%;">날짜</th>
                  </tr>
            """
            for item in results:
                html += f"""
                  <tr>
                    <td>{item['게시판']}</td>
                    <td><a href="{item['링크']}" target="_blank">{item['제목']}</a></td>
                    <td>{item['날짜']}</td>
                  </tr>
                """
            html += """
                </table>
              </body>
            </html>
            """
            return html

        # 이메일 메시지 생성
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"[자동 알림] 방송통신위원회 새 소식 ({datetime.date.today().strftime('%Y-%m-%d')})"
        msg['From'] = SENDER_EMAIL
        msg['To'] = RECEIVER_EMAIL

        email_body = create_email_body(crawled_results)
        part = MIMEText(email_body, 'html')
        msg.attach(part)

        # SMTP 서버를 통해 이메일 발송
        try:
            context = ssl.create_default_context()
            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.starttls(context=context)
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())
            print("이메일이 성공적으로 발송되었습니다!")
        except Exception as e:
            print(f"이메일 발송 중 오류가 발생했습니다: {e}")
        finally:
            if 'server' in locals() and server:
                server.quit()
else:
    print("새로운 게시글이 없어 이메일을 발송하지 않습니다.")
