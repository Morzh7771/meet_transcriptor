from typing import List

 
 

def create_chunks(text: str, max_words: int = 400, overlap_words: int = 100) -> List[str]:
    """Split text into overlapping chunks by lines"""
    if not text.strip():
        return []
    
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    if not lines:
        return []
    
    chunks = []
    i = 0
    
    while i < len(lines):
        chunk_lines, word_count = [], 0
        
        # Build chunk respecting word limit
        while i < len(lines):
            line_words = len(lines[i].split())
            if word_count + line_words > max_words and chunk_lines:
                break
            chunk_lines.append(lines[i])
            word_count += line_words
            i += 1
        
        if chunk_lines:
            chunks.append('\n'.join(chunk_lines))
        
        # Calculate overlap for next chunk
        if i < len(lines):
            overlap_line_count = min(len(chunk_lines), 3)  # Simple overlap strategy
            i -= overlap_line_count
    
    return chunks