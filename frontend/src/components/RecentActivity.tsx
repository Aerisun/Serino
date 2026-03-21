import { Heart, MessageCircle, ArrowUpRight } from "lucide-react";

interface ActivityItem {
  type: "comment" | "like" | "reply";
  user: string;
  avatar: string;
  target: string;
  content?: string;
  date: string;
}

const activities: ActivityItem[] = [
  {
    type: "comment",
    user: "Elena Torres",
    avatar: "https://api.dicebear.com/9.x/notionists/svg?seed=Elena",
    target: "Why Motion Design Matters",
    content: "This resonated deeply — especially the part about easing curves conveying brand personality.",
    date: "3 小时前",
  },
  {
    type: "like",
    user: "Kai Nakamura",
    avatar: "https://api.dicebear.com/9.x/notionists/svg?seed=Kai",
    target: "Why Motion Design Matters",
    date: "5 小时前",
  },
  {
    type: "reply",
    user: "你",
    avatar: "/images/avatar.png",
    target: "Elena Torres",
    content: "Thank you — I think timing is the most underrated design variable we have.",
    date: "4 小时前",
  },
  {
    type: "like",
    user: "Priya Sharma",
    avatar: "https://api.dicebear.com/9.x/notionists/svg?seed=Priya",
    target: "Building Spatial Layouts",
    date: "昨天",
  },
  {
    type: "comment",
    user: "David Okoro",
    avatar: "https://api.dicebear.com/9.x/notionists/svg?seed=David",
    target: "Building Spatial Layouts",
    content: "Saved this for my next project. The layered shadow technique is genius.",
    date: "2 天前",
  },
  {
    type: "reply",
    user: "你",
    avatar: "/images/avatar.png",
    target: "David Okoro",
    content: "Glad it helped — try combining it with concentric radii for an even cleaner result.",
    date: "2 天前",
  },
  {
    type: "like",
    user: "Sofia Lindgren",
    avatar: "https://api.dicebear.com/9.x/notionists/svg?seed=Sofia",
    target: "Type Systems That Actually Scale",
    date: "3 天前",
  },
  {
    type: "comment",
    user: "Sofia Lindgren",
    avatar: "https://api.dicebear.com/9.x/notionists/svg?seed=Sofia",
    target: "Type Systems That Actually Scale",
    content: "This is the type article I wish I had three years ago.",
    date: "3 天前",
  },
];

const RecentActivity = () => {
  return (
    <div className="flex flex-col h-full">
      <div className="flex items-baseline justify-between mb-5">
        <h3 className="text-sm font-body font-medium text-foreground/50 uppercase tracking-widest">
          最近动态
        </h3>
        <a
          href="#"
          className="text-[11px] font-body text-foreground/30 hover:text-foreground/50 transition-colors flex items-center gap-1"
        >
          查看全部 <ArrowUpRight className="h-3 w-3" />
        </a>
      </div>

      <div className="overflow-y-auto max-h-[420px] scrollbar-hide pr-1 -mr-1">
        {activities.map((item, i) => (
          <div key={i}>
            {i > 0 && <div className="border-t border-foreground/[0.05]" />}
            <div className="flex items-start gap-3 py-3.5">
              {/* Avatar */}
              <div className="h-7 w-7 shrink-0 overflow-hidden rounded-full bg-foreground/[0.06] mt-0.5">
                <img
                  src={item.avatar}
                  alt={item.user}
                  className="h-full w-full object-cover"
                  loading="lazy"
                />
              </div>

              {/* Content */}
              <div className="min-w-0 flex-1">
                {item.type === "like" && (
                  <div className="flex items-center gap-1.5">
                    <Heart className="h-3 w-3 text-foreground/20 shrink-0" />
                    <span className="text-[11px] font-body text-foreground/35">
                      <span className="text-foreground/55">{item.user}</span> 赞了{" "}
                      <span className="text-foreground/45">{item.target}</span>
                    </span>
                    <span className="text-[10px] font-body text-foreground/15 ml-auto shrink-0">
                      {item.date}
                    </span>
                  </div>
                )}

                {item.type === "comment" && (
                  <div>
                    <div className="flex items-center gap-1.5">
                      <MessageCircle className="h-3 w-3 text-foreground/20 shrink-0" />
                      <span className="text-[11px] font-body text-foreground/35">
                        <span className="text-foreground/55">{item.user}</span> 评论了{" "}
                        <span className="text-foreground/45">{item.target}</span>
                      </span>
                      <span className="text-[10px] font-body text-foreground/15 ml-auto shrink-0">
                        {item.date}
                      </span>
                    </div>
                    <p className="text-[11px] font-body text-foreground/35 mt-1.5 leading-relaxed pl-[18px]">
                      "{item.content}"
                    </p>
                  </div>
                )}

                {item.type === "reply" && (
                  <div>
                    <div className="flex items-center gap-1.5">
                      <MessageCircle className="h-3 w-3 text-foreground/20 shrink-0" />
                      <span className="text-[11px] font-body text-foreground/35">
                        <span className="text-foreground/55">{item.user}</span> 回复了{" "}
                        <span className="text-foreground/45">{item.target}</span>
                      </span>
                      <span className="text-[10px] font-body text-foreground/15 ml-auto shrink-0">
                        {item.date}
                      </span>
                    </div>
                    <p className="text-[11px] font-body text-foreground/35 mt-1.5 leading-relaxed pl-[18px]">
                      "{item.content}"
                    </p>
                  </div>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default RecentActivity;
