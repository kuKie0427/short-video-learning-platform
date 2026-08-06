export interface Video {
  id: string;
  title: string;
  description: string;
  url: string;
  cover: string;
  author: {
    id: string;
    name: string;
    avatar: string;
  };
  likes: number;
  comments: number;
  shares: number;
}

export const MOCK_VIDEOS: Video[] = [
  {
    id: '00000000-0000-0000-0000-000000000001',
    title: '3分钟学习微积分',
    description: '快速掌握微积分基础概念，数学其实很有趣！ #微积分 #数学 #学习',
    url: '/videos/calculus.mp4',
    cover: 'https://images.unsplash.com/photo-1635070041078-e363dbe005cb?w=800&q=80', // Math related cover
    author: {
      id: 'u1',
      name: '数学之美',
      avatar: 'https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?w=100&q=80',
    },
    likes: 1240,
    comments: 45,
    shares: 88,
  },
  {
    id: '00000000-0000-0000-0000-000000000002',
    title: '雅思3分钟学习',
    description: '雅思口语高分技巧，每天3分钟，轻松开口说英语！ #雅思 #英语 #口语',
    url: '/videos/ielts.mp4',
    cover: 'https://images.unsplash.com/photo-1546410531-bb4caa6b424d?w=800&q=80', // Education/English related cover
    author: {
      id: 'u2',
      name: '英语达人',
      avatar: 'https://images.unsplash.com/photo-1599566150163-29194dcaad36?w=100&q=80',
    },
    likes: 3500,
    comments: 120,
    shares: 500,
  }
];
