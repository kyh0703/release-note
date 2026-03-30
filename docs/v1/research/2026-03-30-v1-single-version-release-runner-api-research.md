# Single-Version Release Runner API Research v1

## Question

`tagging-version` 하나로 Jira 릴리즈 처리와 Confluence 위키 갱신을 Linux 환경에서 브라우저 자동화 없이 끝낼 수 있는가?

## Context

- 대상 Jira 프로젝트는 `IPR`이다.
- 대상 Confluence 공간은 `PAC`이다.
- 사용자가 요구한 런타임 제약은 Linux + API-only이다.
- 조사 기준일은 2026-03-30이며, 실서버는 `qa.bridgetec.co.kr`이다.

## Findings

- Jira `IPR` 프로젝트 REST API는 Basic Auth로 바로 응답한다.
- Jira version 목록은 `/jira/rest/api/2/project/IPR/versions`로 조회 가능하다.
- Jira 릴리즈 노트는 `/jira/secure/ReleaseNote.jspa?projectId=<id>&version=<id>&styleName=Text|Html&Create=Create` 응답의 `textarea`에서 직접 추출 가능하다.
- Confluence 실서버는 `4.2.4`이며 최신 `/rest/api/content`는 없지만 `JSON-RPC`, `SOAP`, `XML-RPC`는 열려 있다.
- Confluence JSON-RPC 엔드포인트 `/wiki/rpc/json-rpc/confluenceservice-v2`는 Basic Auth로 동작한다.
- Confluence에서 `getPage`, `convertWikiToStorageFormat`, `getAttachments`는 실서버 호출로 성공했다.
- Atlassian 공식 문서 기준으로 Confluence 4.x의 `storePage`, `removePage`, `getPage`, `getAttachments`, `addAttachment`가 원격 API 메서드로 제공된다.
- Confluence prototype REST는 검색과 조회에는 유용하지만 쓰기 작업 관점에서는 주 채널로 쓰기 어렵다.
- 실제 PAC 페이지 `IPRON v6.2.0-b4h19`의 storage content는 `ri:attachment`, `ri:page` 참조를 포함한다. 일부 참조는 현재 페이지가 아닌 별도 페이지 title을 명시하고 있어 단순 본문 복사만으로는 UI의 copy 동작과 완전히 같지 않을 수 있다.
- Jira 최신 흐름에서는 다음 patch version이 이미 존재할 수 있으므로 `create`가 아니라 `create-or-skip` 동작이 필요하다.

## Sources

- Atlassian Confluence JSON-RPC APIs:
  - https://developer.atlassian.com/server/confluence/confluence-json-rpc-apis/
- Atlassian Remote Confluence methods:
  - https://developer.atlassian.com/server/confluence/remote-confluence-methods/
- Atlassian Confluence REST APIs - prototype only:
  - https://developer.atlassian.com/server/confluence/confluence-rest-apis-prototype-only/
- Atlassian Confluence 4.2 Admin Guide:
  - https://downloads.atlassian.com/software/confluence/downloads/documentation/Confluence%204.2%20Admin%20Guide%20%28PDF%29%20DOC-20120412.pdf
- Live endpoint checks on `qa.bridgetec.co.kr`:
  - `/jira/rest/api/2/project/IPR`
  - `/jira/rest/api/2/project/IPR/versions`
  - `/jira/secure/ReleaseNote.jspa`
  - `/wiki/rpc/json-rpc/confluenceservice-v2`
  - `/wiki/rpc/soap-axis/confluenceservice-v2?wsdl`
  - `/wiki/rpc/xmlrpc`

## Implications

- v1은 Python 기반 Linux CLI로 정리하는 것이 가장 단순하다.
- Jira는 REST API + `ReleaseNote.jspa` 조합으로 처리할 수 있다.
- Confluence는 HTML form scraping 대신 JSON-RPC로 페이지 조회/생성/수정/삭제를 우선 구현할 수 있다.
- 위키 페이지 생성 시 attachment/reference 보존 전략을 명시적으로 검증해야 한다.
- `dry-run`과 idempotent한 `create-or-skip`이 필수다.

## Follow-ups

- fileserver URL의 정확한 규칙식을 입력 예시로 고정한다.
- 새 Confluence 페이지 생성 시 attachment를 복사해야 하는지, 기존 참조를 유지해야 하는지 테스트 페이지로 검증한다.
- 다음 patch version 계산 규칙을 hotfix/h 계열까지 포함해 명시적으로 테스트한다.
