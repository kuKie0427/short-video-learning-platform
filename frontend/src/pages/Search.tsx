import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search as SearchIcon, X, ArrowLeft, Flame, Filter } from 'lucide-react';
import { searchApi } from '../services/api';
import clsx from 'clsx';
import type { Video } from '../services/mockData';

// Types
interface SearchFilters {
  duration_range?: '0-60' | '60-180';
  sort_by: 'relevance' | 'latest' | 'hot';
  tags: string[];
}

interface SearchResult extends Video {
  // Extend if needed, for now using Video type
}

// 后端搜索API返回的数据结构
interface SearchApiResult {
  video_id: string;
  title: string;
  description?: string;
  cover_url: string;
  play_url?: string;
  duration: number;
  author: {
    id: string;
    nickname: string;
    avatar: string;
  };
  stats: {
    play_count: number;
    like_count: number;
    comment_count: number;
  };
}

// 将后端搜索结果映射为前端Video类型
const mapSearchResultToVideo = (result: SearchApiResult): Video => ({
  id: result.video_id,
  title: result.title,
  description: result.description || '',
  url: result.play_url || '', // 播放URL可能需要在详情页获取
  cover: result.cover_url,
  author: {
    id: result.author.id,
    name: result.author.nickname,
    avatar: result.author.avatar
  },
  likes: result.stats.like_count,
  comments: result.stats.comment_count,
  shares: 0 // 后端暂无分享数
});

export const Search: React.FC = () => {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  
  // Filters
  const [filters, setFilters] = useState<SearchFilters>({
    sort_by: 'relevance',
    tags: []
  });

  // Debounce Logic
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedQuery(query);
    }, 300); // 300ms debounce
    return () => clearTimeout(timer);
  }, [query]);

  // Fetch Suggestions
  useEffect(() => {
    if (debouncedQuery.trim().length > 0 && !hasSearched) {
      searchApi.getSuggestions(debouncedQuery)
        .then(res => setSuggestions(res.data || []))
        .catch(() => setSuggestions([])); // Fail silently
    } else {
      setSuggestions([]);
    }
  }, [debouncedQuery, hasSearched]);

  // Execute Search
  const handleSearch = useCallback(async (searchQuery: string = query) => {
    if (!searchQuery.trim()) return;
    
    setLoading(true);
    setSuggestions([]);
    setHasSearched(true);
    setQuery(searchQuery); // Ensure input matches
    
    try {
      const res = await searchApi.searchVideos({
        q: searchQuery,
        duration_range: filters.duration_range,
        sort_by: filters.sort_by,
        tags: filters.tags.join(',')
      });
      
      console.log('Search API response:', res.data);
      
      // 映射后端数据到前端Video类型
      // 后端响应格式: { code, message, data: { items: [...] } }
      const searchData = res.data?.data || res.data || {};
      const apiResults = searchData.items || [];
      console.log('API results:', apiResults);
      
      const mappedResults = Array.isArray(apiResults) 
        ? apiResults.map(mapSearchResultToVideo).filter(item => item !== null)
        : [];
      
      console.log('Mapped results:', mappedResults);
      
      // 如果后端没有数据，使用mock数据作为后备
      if (mappedResults.length === 0) {
        // 从 mock 数据中搜索
        const { MOCK_VIDEOS } = await import('../services/mockData');
        const mockResults = MOCK_VIDEOS.filter(video => 
          video.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
          video.description.toLowerCase().includes(searchQuery.toLowerCase())
        );
        console.log('Using mock data fallback:', mockResults);
        setResults(mockResults);
      } else {
        setResults(mappedResults);
      }
    } catch (error) {
      console.error('Search failed', error);
      // 失败时使用mock数据
      const { MOCK_VIDEOS } = await import('../services/mockData');
      const mockResults = MOCK_VIDEOS.filter(video => 
        video.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        video.description.toLowerCase().includes(searchQuery.toLowerCase())
      );
      setResults(mockResults);
    } finally {
      setLoading(false);
    }
  }, [filters, query]);

  // Handle Suggestion Click
  const handleSuggestionClick = (suggestion: string) => {
    setQuery(suggestion);
    handleSearch(suggestion);
  };

  // Toggle Tag
  const toggleTag = (tag: string) => {
    setFilters(prev => ({
      ...prev,
      tags: prev.tags.includes(tag) 
        ? prev.tags.filter(t => t !== tag)
        : [...prev.tags, tag]
    }));
  };

  // Effect to re-search when filters change (if already searched)
  useEffect(() => {
    if (hasSearched) {
      handleSearch();
    }
  }, [filters.duration_range, filters.sort_by, filters.tags.length]); // Dependencies for filter changes

  return (
    <div className="flex flex-col h-full bg-white">
      {/* Header & Search Bar */}
      <div className="sticky top-0 bg-white z-20 border-b border-gray-100 px-4 py-3 flex items-center gap-3">
        <button onClick={() => navigate(-1)} className="p-1">
          <ArrowLeft size={24} className="text-gray-600" />
        </button>
        
        <div className="flex-1 relative">
          <div className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400">
            <SearchIcon size={18} />
          </div>
          <input
            type="text"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setHasSearched(false); // Reset search state on typing
            }}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            placeholder="搜索课程、知识点..."
            className="w-full bg-gray-100 rounded-full py-2 pl-10 pr-10 text-sm focus:outline-none focus:ring-2 focus:ring-blue-100"
            autoFocus
          />
          {query && (
            <button 
              onClick={() => { setQuery(''); setHasSearched(false); }}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400"
            >
              <X size={16} />
            </button>
          )}
        </div>

        <button 
          onClick={() => handleSearch()} 
          className="text-blue-600 font-medium text-sm whitespace-nowrap"
        >
          搜索
        </button>
      </div>

      {/* Suggestions Overlay */}
      {!hasSearched && suggestions.length > 0 && (
        <div className="absolute top-[60px] left-0 right-0 bg-white z-30 h-full overflow-y-auto px-4">
          {suggestions.map((s, idx) => (
            <div 
              key={idx}
              onClick={() => handleSuggestionClick(s)}
              className="flex items-center gap-3 py-4 border-b border-gray-50 active:bg-gray-50"
            >
              <SearchIcon size={16} className="text-gray-400" />
              <span className="text-gray-700">{s}</span>
            </div>
          ))}
        </div>
      )}

      {/* Filter Bar */}
      <div className="px-4 py-3 border-b border-gray-100 overflow-x-auto no-scrollbar">
        <div className="flex items-center gap-2 min-w-max">
          <div className="flex items-center gap-1 mr-2 text-gray-500 text-xs font-bold">
            <Filter size={14} />
            筛选
          </div>

          {/* Duration Filter */}
          <select 
            className="bg-gray-100 text-xs px-3 py-1.5 rounded-full border-none outline-none text-gray-700 appearance-none font-medium"
            value={filters.duration_range || ''}
            onChange={(e) => setFilters(prev => ({ ...prev, duration_range: e.target.value as any || undefined }))}
          >
            <option value="">全部时长</option>
            <option value="0-60">1分钟内</option>
            <option value="60-180">1-3分钟</option>
          </select>

          {/* Sort Filter */}
          <div className="flex bg-gray-100 rounded-full p-0.5">
            {[
              { id: 'relevance', label: '综合' },
              { id: 'latest', label: '最新' },
              { id: 'hot', label: '最热' }
            ].map(opt => (
              <button
                key={opt.id}
                onClick={() => setFilters(prev => ({ ...prev, sort_by: opt.id as any }))}
                className={clsx(
                  "px-3 py-1 rounded-full text-xs font-medium transition-colors",
                  filters.sort_by === opt.id ? "bg-white shadow-sm text-blue-600" : "text-gray-500"
                )}
              >
                {opt.label}
              </button>
            ))}
          </div>

          {/* Tags */}
          <div className="w-[1px] h-4 bg-gray-200 mx-1" />
          {['编程', '英语', '健身'].map(tag => (
            <button
              key={tag}
              onClick={() => toggleTag(tag)}
              className={clsx(
                "px-3 py-1.5 rounded-full text-xs font-medium border transition-colors",
                filters.tags.includes(tag)
                  ? "bg-blue-50 border-blue-200 text-blue-600"
                  : "bg-white border-gray-200 text-gray-600"
              )}
            >
              {tag}
            </button>
          ))}
        </div>
      </div>

      {/* Results List */}
      <div className="flex-1 overflow-y-auto bg-gray-50 p-2">
        {loading ? (
          <div className="flex flex-col items-center justify-center pt-20 text-gray-400">
            <div className="w-8 h-8 border-4 border-blue-200 border-t-blue-500 rounded-full animate-spin mb-4" />
            <p className="text-sm">正在搜索...</p>
          </div>
        ) : hasSearched && results.length === 0 ? (
          <div className="flex flex-col items-center justify-center pt-20 text-gray-400">
            <SearchIcon size={48} className="mb-4 opacity-20" />
            <p className="text-sm">未找到相关课程</p>
            <p className="text-xs mt-1">换个关键词试试看</p>
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-2">
            {results.map((video) => (
              <div 
                key={video.id} 
                className="bg-white rounded-lg overflow-hidden shadow-sm active:scale-95 transition-transform"
                onClick={() => navigate(`/video/${video.id}?from=search`)}
              >
                <div className="aspect-[3/4] relative bg-gray-200">
                  <img src={video.cover} alt={video.title} className="w-full h-full object-cover" />
                  <div className="absolute bottom-1 right-1 bg-black/60 text-white text-[10px] px-1.5 py-0.5 rounded backdrop-blur-sm">
                    {/* Mock Duration */}
                    02:30
                  </div>
                </div>
                <div className="p-2">
                  <h3 className="text-sm font-bold line-clamp-2 mb-1 leading-snug">{video.title}</h3>
                  <div className="flex items-center gap-1.5">
                    <img src={video.author.avatar} alt="" className="w-4 h-4 rounded-full" />
                    <span className="text-[10px] text-gray-500 truncate">{video.author.name}</span>
                  </div>
                  <div className="flex items-center justify-between mt-2 text-[10px] text-gray-400">
                    <span className="flex items-center gap-0.5">
                      <Flame size={10} /> {video.likes}
                    </span>
                    <span>2天前</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
